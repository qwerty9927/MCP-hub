"""SQLAlchemy model for MCP Sessions."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums.session_enum import SessionStatus
from app.domain.session_entity import SessionEntity
from app.models.base_model import Base


class SessionModel(Base):
    """Database representation of an MCP client session."""

    __tablename__ = "mcp_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))
    title: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    api_key_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)
    client_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idle_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

    __table_args__ = (
        Index("ix_mcp_sessions_user_fingerprint_activity", "user_id", "client_fingerprint", "last_activity_at"),
        # The background job's lookup of active Sessions by idle time.
        Index("ix_mcp_sessions_status_activity", "status", "last_activity_at"),
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
            id=UUID(self.id),
            title=self.title,
            status=SessionStatus(self.status) if self.status in SessionStatus._value2member_map_ else SessionStatus.ACTIVE,
            metadata=self.metadata_json,
            created_at=self.created_at,
            last_activity_at=self.last_activity_at,
            total_tool_calls=total_tool_calls,
            user_id=UUID(self.user_id),
            api_key_id=UUID(self.api_key_id) if self.api_key_id else None,
            client_fingerprint=self.client_fingerprint,
            idle_timeout_seconds=self.idle_timeout_seconds,
        )

    @classmethod
    def from_domain(cls, entity: SessionEntity) -> "SessionModel":
        """Convert domain entity to database model."""
        return cls(
            id=str(entity.id),
            title=entity.title,
            status=str(entity.status.value) if hasattr(entity.status, "value") else str(entity.status),
            metadata_json=entity.metadata,
            created_at=entity.created_at,
            last_activity_at=entity.last_activity_at,
            user_id=str(entity.user_id),
            api_key_id=str(entity.api_key_id) if entity.api_key_id else None,
            client_fingerprint=entity.client_fingerprint,
            idle_timeout_seconds=entity.idle_timeout_seconds,
        )
