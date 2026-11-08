"""SQLAlchemy model for tool execution history."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums.session_enum import ToolCallStatus
from app.domain.execution_entity import ExecutionEntity
from app.domain.session_entity import ToolCallEntity
from app.models.base_model import Base


class ExecutionModel(Base):
    """Database representation of an executed tool call."""

    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    server_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        nullable=False,
    )
    response: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("mcp_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="completed", index=True, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_tool_executions_session_started_at", "session_id", "started_at"),
        Index("ix_tool_executions_session_status", "session_id", "status"),
    )

    # Relationships
    server = relationship("ServerModel", back_populates="executions")
    session = relationship("SessionModel", back_populates="executions")

    def to_domain(self) -> ExecutionEntity:
        """Convert database model to domain entity."""
        return ExecutionEntity(
            id=UUID(self.id),
            server_id=UUID(self.server_id),
            server_name=self.server_name,
            tool_name=self.tool_name,
            arguments=self.arguments,
            is_error=self.is_error,
            error_message=self.error_message,
            duration_ms=self.duration_ms,
            executed_at=self.executed_at,
            response=self.response,
            session_id=self.session_id,
            status=self.status,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )

    def to_tool_call_domain(self) -> ToolCallEntity:
        """Convert database model to ToolCallEntity for session explorer."""
        status_val = (
            ToolCallStatus(self.status)
            if self.status in ToolCallStatus._value2member_map_
            else (ToolCallStatus.FAILED if self.is_error else ToolCallStatus.COMPLETED)
        )
        return ToolCallEntity(
            id=UUID(self.id),
            session_id=self.session_id,
            server_name=self.server_name,
            tool_name=self.tool_name,
            status=status_val,
            started_at=self.started_at or self.executed_at,
            completed_at=self.completed_at,
            duration_ms=self.duration_ms,
            error_summary=self.error_message,
            arguments=self.arguments or {},
            response=self.response,
        )

    @classmethod
    def from_domain(cls, entity: ExecutionEntity) -> "ExecutionModel":
        """Convert domain entity to database model."""
        return cls(
            id=str(entity.id),
            server_id=str(entity.server_id),
            server_name=entity.server_name,
            tool_name=entity.tool_name,
            arguments=entity.arguments,
            is_error=entity.is_error,
            error_message=entity.error_message,
            duration_ms=entity.duration_ms,
            executed_at=entity.executed_at,
            response=entity.response,
            session_id=str(entity.session_id) if entity.session_id else None,
            status=entity.status or ("failed" if entity.is_error else "completed"),
            started_at=entity.started_at or entity.executed_at,
            completed_at=entity.completed_at,
        )
