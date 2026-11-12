"""Session Explorer service for querying sessions and tool execution history."""

import math
import re
from typing import Any
from uuid import UUID, uuid4

from app.core.enums.session_enum import SessionStatus
from app.core.exceptions import NotFoundError
from app.domain.session_entity import SessionEntity
from app.infrastructure.repositories.execution_repository import ExecutionRepositoryAbstract
from app.infrastructure.repositories.session_repository import SessionRepositoryAbstract
from app.schemas.common_schema import PaginatedResponse
from app.schemas.session_schema import (
    SessionCreateRequest,
    SessionDetailResponse,
    SessionResponse,
    ToolCallResponse,
)

# Additional regex patterns for sensitive payload keys
SENSITIVE_KEY_REGEX = re.compile(
    r"(token|secret|password|passwd|api_?key|auth|credential|private_?key)",
    re.IGNORECASE,
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


class SessionExplorerService:
    """Orchestrates session discovery, metrics calculation, and tool call history."""

    def __init__(
        self,
        session_repository: SessionRepositoryAbstract,
        execution_repository: ExecutionRepositoryAbstract,
    ) -> None:
        self.session_repo = session_repository
        self.execution_repo = execution_repository

    async def create_session(self, payload: SessionCreateRequest) -> SessionResponse:
        """Explicitly create a new session."""
        session_id = uuid4().hex
        entity = SessionEntity(
            id=session_id,
            title=payload.title or f"Session {session_id[:8]}",
            status=SessionStatus.ACTIVE,
            metadata=payload.metadata,
        )
        created = await self.session_repo.create(entity)
        return SessionResponse(
            id=created.id,
            title=created.title,
            status=created.status.value if hasattr(created.status, "value") else str(created.status),
            created_at=created.created_at,
            last_activity_at=created.last_activity_at,
            total_tool_calls=0,
        )

    async def list_sessions(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
    ) -> PaginatedResponse[SessionResponse]:
        """Retrieve paginated sessions with optional search and status filtering."""
        items, total = await self.session_repo.list(
            page=page,
            page_size=page_size,
            search=search,
            status=status,
        )

        records = [
            SessionResponse(
                id=s.id,
                title=s.title,
                status=s.status.value if hasattr(s.status, "value") else str(s.status),
                created_at=s.created_at,
                last_activity_at=s.last_activity_at,
                total_tool_calls=s.total_tool_calls,
            )
            for s in items
        ]

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse[SessionResponse](
            items=records,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_session(self, session_id: str) -> SessionDetailResponse:
        """Retrieve detailed session view by ID including aggregated metrics."""
        detail = await self.session_repo.get_by_id(session_id)
        if not detail:
            raise NotFoundError(
                f"Session with id '{session_id}' not found",
                details={"session_id": session_id},
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
        session_id: str,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        order: str = "asc",
        status: str | None = None,
        server_name: str | None = None,
        tool_name: str | None = None,
    ) -> PaginatedResponse[ToolCallResponse]:
        """Retrieve all tool calls belonging to a session in chronological order."""
        # 1. Verify session exists
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise NotFoundError(
                f"Session with id '{session_id}' not found",
                details={"session_id": session_id},
            )

        # 2. Query execution records
        items, total = await self.execution_repo.list_by_session(
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

    async def get_session_tool_call(self, session_id: str, call_id: UUID) -> ToolCallResponse:
        """Retrieve a specific tool call within a session."""
        # 1. Verify session exists
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise NotFoundError(
                f"Session with id '{session_id}' not found",
                details={"session_id": session_id},
            )

        # 2. Query tool call
        call = await self.execution_repo.get_tool_call(session_id, call_id)
        if not call:
            raise NotFoundError(
                f"Tool call with id '{call_id}' not found in session '{session_id}'",
                details={"session_id": session_id, "call_id": str(call_id)},
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
