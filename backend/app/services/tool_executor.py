"""Execution module: resolve, check, validate, call, and audit a single Tool invocation.

This is the only place that decides whether an attempt may reach a downstream Server and how it is
recorded (see GLOSSARY.md "Execution" and docs/adr/0002-what-counts-as-an-execution.md). Callers
(the MULTI_EXECUTE_TOOLS meta-tool, the REST execute route) are thin adapters over `execute`.
"""

import asyncio
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import mcp.types as mcp_types

from app.core.enums.execution_enum import ExecutionOutcomeKind, RejectionReason
from app.core.enums.session_enum import ToolCallStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger
from app.domain.execution_entity import ExecutionEntity
from app.domain.server_entity import ServerEntity
from app.domain.tool_entity import ToolEntity
from app.helpers.errors import format_mcp_error
from app.helpers.validation import validate_tool_arguments
from app.infrastructure.repositories.execution_repository import ExecutionRepositoryAbstract
from app.infrastructure.repositories.session_repository import SessionRepositoryAbstract
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService, split_qualified_tool_id

TOOL_ERROR_FALLBACK_MESSAGE = "Tool execution reported an error"

_RECORDED_STATUS: dict[ExecutionOutcomeKind, ToolCallStatus] = {
    ExecutionOutcomeKind.SUCCEEDED: ToolCallStatus.COMPLETED,
    ExecutionOutcomeKind.TOOL_ERROR: ToolCallStatus.FAILED,
    ExecutionOutcomeKind.FAILED: ToolCallStatus.FAILED,
    ExecutionOutcomeKind.REJECTED: ToolCallStatus.REJECTED,
}


@dataclass(frozen=True)
class ExecutionOutcome:
    """The classified result of one attempt to execute a Tool."""

    kind: ExecutionOutcomeKind
    tool_reference: str
    executed_at: datetime
    rejection_reason: RejectionReason | None = None
    execution_id: UUID | None = None  # None when no Execution was recorded (unknown Tool Reference)
    server_id: UUID | None = None
    server_name: str | None = None
    tool_name: str | None = None
    content: list[dict[str, Any]] = field(default_factory=list)
    structured_content: Any | None = None
    error_message: str | None = None
    duration_ms: float = 0.0


class _Unresolved(Exception):
    """Private control flow: the Tool Reference could not be resolved to a Tool, for a known reason."""

    def __init__(self, kind: ExecutionOutcomeKind, message: str, reason: RejectionReason | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.reason = reason


def _server_disabled_message(server: ServerEntity) -> str:
    return f"Server '{server.name}' is disabled. Enable it before performing this operation."


def _content_blocks(result: mcp_types.CallToolResult) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for block in result.content or []:
        if hasattr(block, "model_dump"):
            blocks.append(block.model_dump(exclude_none=True))
        elif isinstance(block, dict):
            blocks.append(block)
        else:
            blocks.append({"type": "text", "text": str(block)})
    return blocks


def _tool_error_message(blocks: list[dict[str, Any]]) -> str:
    texts = [b["text"] for b in blocks if b.get("type") == "text" and b.get("text")]
    return "\n".join(texts) if texts else TOOL_ERROR_FALLBACK_MESSAGE


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


class ToolExecutor:
    """Executes Tools on downstream Servers and records every resolved attempt as an Execution."""

    def __init__(
        self,
        server_registry: ServerRegistryService,
        connection_manager: ConnectionManager,
        tool_catalog: ToolCatalogService,
        execution_repository: ExecutionRepositoryAbstract,
        session_repository: SessionRepositoryAbstract | None = None,
    ) -> None:
        self._server_registry = server_registry
        self._connection_manager = connection_manager
        self._tool_catalog = tool_catalog
        self._execution_repository = execution_repository
        self._session_repository = session_repository

    async def execute(
        self,
        tool_reference: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
        timeout: float | None = None,
    ) -> ExecutionOutcome:
        """Execute the Tool named by `tool_reference` and return its Outcome.

        Expected outcomes (unknown Tool, disabled Server, unavailable Tool, invalid arguments, downstream
        errors and faults) are returned, never raised. Only faults in the hub's own infrastructure raise,
        plus `asyncio.CancelledError`, which is recorded and then re-raised.
        """
        executed_at = datetime.now(UTC)

        try:
            tool = await self._resolve(tool_reference)
            server = await self._server_for(tool) if tool else None
            if tool is None or server is None:
                raise _Unresolved(
                    ExecutionOutcomeKind.REJECTED,
                    f"Unknown or unavailable tool: '{tool_reference}'",
                    RejectionReason.UNKNOWN_TOOL,
                )
        except _Unresolved as unresolved:
            # No Tool, so no Execution (ADR-0002): only Session activity and a log line.
            logger.warning(
                f"Unresolved Tool Reference '{tool_reference}': {unresolved.message}",
                extra={
                    "event": "tool_reference_unresolved",
                    "tool_reference": tool_reference,
                    "session_id": session_id,
                    "outcome": unresolved.kind.value,
                    "rejection_reason": unresolved.reason.value if unresolved.reason else None,
                },
            )
            await self._touch_session(session_id)
            return ExecutionOutcome(
                kind=unresolved.kind,
                rejection_reason=unresolved.reason,
                tool_reference=tool_reference,
                executed_at=executed_at,
                error_message=unresolved.message,
            )

        rejection = self._rejection_for(server, tool, arguments)
        if rejection is not None:
            reason, message = rejection
            outcome = ExecutionOutcome(
                kind=ExecutionOutcomeKind.REJECTED,
                rejection_reason=reason,
                tool_reference=tool_reference,
                executed_at=executed_at,
                execution_id=uuid4(),
                server_id=server.id,
                server_name=server.name,
                tool_name=tool.name,
                error_message=message,
            )
            await self._record(outcome, arguments, session_id, started_at=executed_at)
            return outcome

        outcome = await self._call(server, tool, tool_reference, arguments, session_id, timeout, executed_at)
        await self._record(outcome, arguments, session_id, started_at=executed_at)
        return outcome

    async def _resolve(self, tool_reference: str) -> ToolEntity | None:
        tool = await self._tool_catalog.resolve(tool_reference)
        if tool is not None:
            return tool

        # Refresh-on-miss is only possible when the reference names its Server (Qualified Tool ID).
        server_id, _ = split_qualified_tool_id(tool_reference)
        if server_id is None:
            return None
        try:
            server = await self._server_registry.get_server_entity(server_id)
        except NotFoundError:
            return None
        if not server.enabled:
            raise _Unresolved(ExecutionOutcomeKind.REJECTED, _server_disabled_message(server), RejectionReason.SERVER_DISABLED)

        try:
            refreshed = await self._tool_catalog.refresh_server_tools(server, self._connection_manager)
        except Exception as exc:
            message = f"Could not refresh tools from server '{server.name}': {format_mcp_error(exc)}"
            raise _Unresolved(ExecutionOutcomeKind.FAILED, message) from exc
        await self._server_registry.update_health(server.id, server.health_status, len(refreshed))
        return await self._tool_catalog.resolve(tool_reference)

    async def _server_for(self, tool: ToolEntity) -> ServerEntity | None:
        try:
            return await self._server_registry.get_server_entity(tool.server_id)
        except NotFoundError:
            return None

    @staticmethod
    def _rejection_for(server: ServerEntity, tool: ToolEntity, arguments: dict[str, Any]) -> tuple[RejectionReason, str] | None:
        if not server.enabled:
            return RejectionReason.SERVER_DISABLED, _server_disabled_message(server)
        if tool.availability_status != "AVAILABLE":
            return (
                RejectionReason.TOOL_UNAVAILABLE,
                f"Tool '{tool.name}' on server '{server.name}' is {tool.availability_status.lower()}",
            )
        try:
            validate_tool_arguments(arguments, tool.input_schema, tool.name)
        except ValidationError as err:
            return RejectionReason.INVALID_ARGUMENTS, err.message
        return None

    async def _call(
        self,
        server: ServerEntity,
        tool: ToolEntity,
        tool_reference: str,
        arguments: dict[str, Any],
        session_id: str | None,
        timeout: float | None,
        executed_at: datetime,
    ) -> ExecutionOutcome:
        attempt = ExecutionOutcome(
            kind=ExecutionOutcomeKind.FAILED,
            tool_reference=tool_reference,
            executed_at=executed_at,
            execution_id=uuid4(),
            server_id=server.id,
            server_name=server.name,
            tool_name=tool.name,
        )
        start = time.perf_counter()
        try:
            result = await self._connection_manager.call_tool(server=server, tool_name=tool.name, arguments=arguments, timeout=timeout)
        except asyncio.CancelledError:
            cancelled = replace(attempt, error_message="cancelled", duration_ms=_elapsed_ms(start))
            await self._record(cancelled, arguments, session_id, started_at=executed_at)
            raise
        except Exception as exc:
            return replace(attempt, error_message=format_mcp_error(exc), duration_ms=_elapsed_ms(start))
        duration_ms = _elapsed_ms(start)

        blocks = _content_blocks(result)
        is_tool_error = bool(result.is_error)
        return replace(
            attempt,
            kind=ExecutionOutcomeKind.TOOL_ERROR if is_tool_error else ExecutionOutcomeKind.SUCCEEDED,
            content=blocks,
            structured_content=getattr(result, "structured_content", None),
            error_message=_tool_error_message(blocks) if is_tool_error else None,
            duration_ms=duration_ms,
        )

    async def _record(
        self,
        outcome: ExecutionOutcome,
        arguments: dict[str, Any],
        session_id: str | None,
        started_at: datetime,
    ) -> None:
        """Persist the Execution; a failed write is logged, never surfaced (the call may have had side effects)."""
        assert outcome.execution_id is not None and outcome.server_id is not None
        completed_at = datetime.now(UTC)
        response: dict[str, Any] | None = None
        if outcome.kind in (ExecutionOutcomeKind.SUCCEEDED, ExecutionOutcomeKind.TOOL_ERROR):
            response = {"content": outcome.content}
            if outcome.structured_content is not None:
                response["structured_content"] = outcome.structured_content

        record = ExecutionEntity(
            id=outcome.execution_id,
            server_id=outcome.server_id,
            server_name=outcome.server_name or "",
            tool_name=outcome.tool_name or "",
            arguments=arguments,
            is_error=outcome.kind != ExecutionOutcomeKind.SUCCEEDED,
            duration_ms=outcome.duration_ms,
            executed_at=outcome.executed_at,
            error_message=outcome.error_message,
            response=response,
            session_id=session_id,
            status=_RECORDED_STATUS[outcome.kind].value,
            started_at=started_at,
            completed_at=completed_at,
        )
        try:
            await self._execution_repository.create(record)
        except Exception as exc:
            logger.error(f"Failed to record Execution {outcome.execution_id} ({outcome.kind}) for '{outcome.tool_reference}': {exc}")
        await self._touch_session(session_id, completed_at)

    async def _touch_session(self, session_id: str | None, timestamp: datetime | None = None) -> None:
        if not session_id or self._session_repository is None:
            return
        try:
            await self._session_repository.update_activity(session_id, timestamp or datetime.now(UTC))
        except Exception as exc:
            logger.error(f"Failed to update activity for session '{session_id}': {exc}")
