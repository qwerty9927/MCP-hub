"""SQLAlchemy model for MCP Sessions."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums.session_enum import SessionStatus
from app.domain.session_entity import SessionEntity
from app.models.base_model import Base


class SessionModel(Base):
    """Database representation of an MCP client session."""

    __tablename__ = "mcp_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        nullable=False,
    )

    # Relationship to execution records
    executions = relationship(
        "ExecutionModel",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def to_domain(self, total_tool_calls: int = 0) -> SessionEntity:
        """Convert database model to domain entity."""
        return SessionEntity(
            id=self.id,
            title=self.title,
            status=SessionStatus(self.status)
            if self.status in SessionStatus._value2member_map_
            else SessionStatus.ACTIVE,
            metadata=self.metadata_json,
            created_at=self.created_at,
            last_activity_at=self.last_activity_at,
            total_tool_calls=total_tool_calls,
        )

    @classmethod
    def from_domain(self, entity: SessionEntity) -> "SessionModel":
        """Convert domain entity to database model."""
        return self(
            id=str(entity.id),
            title=entity.title,
            status=str(entity.status.value)
            if hasattr(entity.status, "value")
            else str(entity.status),
            metadata_json=entity.metadata,
            created_at=entity.created_at,
            last_activity_at=entity.last_activity_at,
        )
