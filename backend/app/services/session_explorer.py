"""Session Explorer service for querying sessions and tool execution history."""

import math
import re
from typing import Any
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.infrastructure.repositories.execution_repository import ExecutionRepositoryAbstract
from app.infrastructure.repositories.session_repository import SessionRepositoryAbstract
from app.schemas.common_schema import PaginatedResponse
from app.schemas.session_schema import (
    SessionDetailResponse,
    SessionResponse,
    ToolCallResponse,
)

# Additional regex patterns for sensitive payload keys
SENSITIVE_KEY_REGEX = re.compile(
    r"(token|secret|password|passwd|api_?key|auth|credential|private_?key)",
    re.IGNORECASE,
)


class SessionExplorerService:
    """Orchestrates session discovery, metrics calculation, and tool call history."""

    def __init__(
        self,
        session_repository: SessionRepositoryAbstract,
        execution_repository: ExecutionRepositoryAbstract,
    ) -> None:
        self._session_repository = session_repository
        self._execution_repository = execution_repository

    async def list_sessions(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
        *,
        user_id: UUID,
    ) -> PaginatedResponse[SessionResponse]:
        """Retrieve paginated sessions with optional search and status filtering."""
        items, total = await self._session_repository.list(
            page=page,
            page_size=page_size,
            search=search,
            status=status,
            user_id=user_id,
        )

        records = [
            SessionResponse(
                id=session.id,
                title=session.title,
                status=session.status.value if hasattr(session.status, "value") else str(session.status),
                created_at=session.created_at,
                last_activity_at=session.last_activity_at,
                total_tool_calls=session.total_tool_calls,
            )
            for session in items
        ]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse[SessionResponse](
            items=records,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_session(self, session_id: UUID, *, user_id: UUID) -> SessionDetailResponse:
        """Retrieve detailed session view by ID including aggregated metrics."""
        detail = await self._session_repository.get_by_id(session_id, user_id=user_id)
        if not detail:
            raise NotFoundError(
                f"Session with id '{session_id}' not found",
                details={"session_id": str(session_id)},
            )

        return SessionDetailResponse(
            id=detail.id,
            title=detail.title,
            metadata=mask_sensitive_data(detail.metadata) if detail.metadata else None,
            status=detail.status.value if hasattr(detail.status, "value") else str(detail.status),
            created_at=detail.created_at,
            last_activity_at=detail.last_activity_at,
            total_tool_calls=detail.total_tool_calls,
            successful_tool_calls=detail.successful_tool_calls,
            failed_tool_calls=detail.failed_tool_calls,
            rejected_tool_calls=detail.rejected_tool_calls,
        )

    async def list_session_tool_calls(
        self,
        session_id: UUID,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        order: str = "asc",
        status: str | None = None,
        server_name: str | None = None,
        tool_name: str | None = None,
        *,
        user_id: UUID,
    ) -> PaginatedResponse[ToolCallResponse]:
        """Retrieve all tool calls belonging to a session in chronological order."""
        # 1. Verify session exists
        session = await self._session_repository.get_by_id(session_id, user_id=user_id)
        if not session:
            raise NotFoundError(
                f"Session with id '{session_id}' not found",
                details={"session_id": str(session_id)},
            )

        # 2. Query execution records
        items, total = await self._execution_repository.list_by_session(
            session_id=session_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            order=order,
            status=status,
            server_name=server_name,
            tool_name=tool_name,
        )

        records = [
            ToolCallResponse(
                id=call.id,
                session_id=call.session_id,
                server_name=call.server_name,
                tool_name=call.tool_name,
                status=call.status.value if hasattr(call.status, "value") else str(call.status),
                started_at=call.started_at,
                completed_at=call.completed_at,
                duration_ms=call.duration_ms,
                error_summary=call.error_summary,
                arguments=mask_sensitive_data(call.arguments),
                response=mask_sensitive_data(call.response) if call.response else None,
            )
            for call in items
        ]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse[ToolCallResponse](
            items=records,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_session_tool_call(self, session_id: UUID, call_id: UUID, *, user_id: UUID) -> ToolCallResponse:
        """Retrieve a specific tool call within a session."""
        # 1. Verify session exists
        session = await self._session_repository.get_by_id(session_id, user_id=user_id)
        if not session:
            raise NotFoundError(
                f"Session with id '{session_id}' not found",
                details={"session_id": str(session_id)},
            )

        # 2. Query tool call
        call = await self._execution_repository.get_tool_call(session_id, call_id)
        if not call:
            raise NotFoundError(
                f"Tool call with id '{call_id}' not found in session '{session_id}'",
                details={"session_id": str(session_id), "call_id": str(call_id)},
            )

        return ToolCallResponse(
            id=call.id,
            session_id=call.session_id,
            server_name=call.server_name,
            tool_name=call.tool_name,
            status=call.status.value if hasattr(call.status, "value") else str(call.status),
            started_at=call.started_at,
            completed_at=call.completed_at,
            duration_ms=call.duration_ms,
            error_summary=call.error_summary,
            arguments=mask_sensitive_data(call.arguments),
            response=mask_sensitive_data(call.response) if call.response else None,
        )


def mask_sensitive_data(value: Any) -> Any:
    """Recursively mask sensitive values in dictionaries and lists."""
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for k, v in value.items():
            if SENSITIVE_KEY_REGEX.search(str(k)):
                masked[k] = "***MASKED***"
            else:
                masked[k] = mask_sensitive_data(v)
        return masked
    elif isinstance(value, list):
        return [mask_sensitive_data(item) for item in value]
    elif isinstance(value, tuple):
        return tuple(mask_sensitive_data(item) for item in value)
    return value
