"""SQLAlchemy model for discovered MCP tools."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.tool_entity import ToolEntity
from app.models.base_model import Base


class ToolModel(Base):
    """Database representation of a discovered tool from an MCP server."""

    __tablename__ = "discovered_tools"

    # Server-qualified ID: "{server_id}:{tool_name}"
    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    server_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    server_name: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    availability_status: Mapped[str] = mapped_column(
        String(20), default="AVAILABLE", index=True, nullable=False
    )
    last_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationship to parent server
    server = relationship("ServerModel", back_populates="tools")

    def to_domain(self) -> ToolEntity:
        """Convert database model to domain entity."""
        return ToolEntity(
            id=self.id,
            server_id=UUID(self.server_id),
            server_name=self.server_name,
            name=self.name,
            description=self.description,
            input_schema=self.input_schema or {},
            availability_status=self.availability_status,
            last_discovered_at=self.last_discovered_at,
        )

    @classmethod
    def from_domain(cls, entity: ToolEntity) -> "ToolModel":
        """Convert domain entity to database model."""
        return cls(
            id=entity.id,
            server_id=str(entity.server_id),
            server_name=entity.server_name,
            name=entity.name,
            description=entity.description,
            input_schema=entity.input_schema or {},
            availability_status=entity.availability_status,
            last_discovered_at=entity.last_discovered_at,
        )
