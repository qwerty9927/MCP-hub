"""Tool Execution Router service."""

import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import mcp.types as mcp_types

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
)
from app.core.logging import get_correlation_id
from app.domain.execution_entity import ExecutionEntity
from app.helpers.validation import validate_tool_arguments
from app.infrastructure.repositories.execution_repo import ExecutionRepositoryAbstract
from app.schemas.tool import ToolExecuteResponse
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService


class ToolRouterService:
    """Validates, routes, and executes MCP tools across registered servers."""

    def __init__(
        self,
        server_registry: ServerRegistryService,
        connection_manager: ConnectionManager,
        tool_catalog: ToolCatalogService,
        execution_repository: ExecutionRepositoryAbstract,
    ) -> None:
        self.server_registry = server_registry
        self.connection_manager = connection_manager
        self.tool_catalog = tool_catalog
        self.execution_repository = execution_repository

    async def execute_mcp_tool(
        self,
        server_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
        execution_id: UUID | None = None,
    ) -> mcp_types.CallToolResult:
        """Route and execute a tool call, returning the native CallToolResult while logging execution."""
        exec_id = execution_id or uuid4()
        now = datetime.now(UTC)
        start_time = time.perf_counter()

        # 1. Validate target server
        server = await self.server_registry.get_server_entity(server_id)
        if not server.enabled:
            raise BadRequestError(
                f"Server '{server_id}' is disabled. Enable it before performing this operation.",
                details={"server_id": str(server_id)},
            )

        # 2. Validate tool presence (try cache or refresh if needed)
        try:
            tool = await self.tool_catalog.get_tool(tool_name, server_id=server_id)
        except NotFoundError:
            # Refresh server tools in case it's newly connected
            refreshed = await self.tool_catalog.refresh_server_tools(
                server, self.connection_manager
            )
            await self.server_registry.update_health(
                server.id, server.health_status, len(refreshed)
            )
            tool = await self.tool_catalog.get_tool(tool_name, server_id=server_id)

        # 3. Validate arguments against tool input schema
        validate_tool_arguments(arguments, tool.input_schema, tool_name)

        # 4. Invoke MCP tool via downstream connection session
        try:
            result = await self.connection_manager.call_tool(
                server=server,
                tool_name=tool_name,
                arguments=arguments,
                timeout=timeout,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Record successful execution log
            log_record = ExecutionEntity(
                id=exec_id,
                server_id=server.id,
                server_name=server.name,
                tool_name=tool_name,
                arguments=arguments,
                is_error=bool(result.is_error),
                duration_ms=round(duration_ms, 2),
                executed_at=now,
                error_message=None,
            )
            await self.execution_repository.create(log_record)
            return result

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_record = ExecutionEntity(
                id=exec_id,
                server_id=server.id,
                server_name=server.name,
                tool_name=tool_name,
                arguments=arguments,
                is_error=True,
                duration_ms=round(duration_ms, 2),
                executed_at=now,
                error_message=str(exc),
            )
            await self.execution_repository.create(log_record)
            raise

    async def execute_tool(
        self,
        server_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> ToolExecuteResponse:
        """Route and execute a tool call with validation, monitoring, and audit logging."""
        execution_id = uuid4()
        now = datetime.now(UTC)
        start_time = time.perf_counter()

        result = await self.execute_mcp_tool(
            server_id=server_id,
            tool_name=tool_name,
            arguments=arguments,
            timeout=timeout,
            execution_id=execution_id,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Extract content blocks for REST API response
        content_items: list[dict[str, Any]] = []
        if result.content:
            for block in result.content:
                if hasattr(block, "model_dump"):
                    content_items.append(block.model_dump())
                elif isinstance(block, dict):
                    content_items.append(block)
                else:
                    content_items.append({"type": "text", "text": str(block)})

        structured_content = getattr(result, "structured_content", None)

        return ToolExecuteResponse(
            execution_id=execution_id,
            server_id=server_id,
            tool_name=tool_name,
            is_error=bool(result.is_error),
            content=content_items,
            structured_content=structured_content,
            duration_ms=round(duration_ms, 2),
            executed_at=now,
            correlation_id=get_correlation_id(),
        )
