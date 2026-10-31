"""SQLAlchemy model for tool execution history."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities import ExecutionEntity
from app.infrastructure.database import Base
from app.models.types import EncryptedJSON


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
    arguments: Mapped[dict[str, Any]] = mapped_column(EncryptedJSON, default=dict, nullable=False)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        nullable=False,
    )

    # Relationship to parent server
    server = relationship("ServerModel", back_populates="executions")

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
        )
