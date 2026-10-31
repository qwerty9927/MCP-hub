"""SQLAlchemy model for MCP Server configurations."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities import ServerEntity
from app.infrastructure.database import Base
from app.schemas.server import HttpConfig, ServerHealthStatus, StdioConfig, TransportType


class ServerModel(Base):
    """Database representation of an MCP Server."""

    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    transport: Mapped[str] = mapped_column(String(20), nullable=False)
    stdio_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    http_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    health_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", nullable=False)
    last_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    discovered_tool_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships to tools and executions
    tools = relationship("ToolModel", back_populates="server", cascade="all, delete-orphan")
    executions = relationship(
        "ExecutionModel", back_populates="server", cascade="all, delete-orphan"
    )

    def to_domain(self) -> ServerEntity:
        """Convert database model to domain entity."""
        return ServerEntity(
            id=UUID(self.id),
            name=self.name,
            description=self.description,
            transport=TransportType(self.transport),
            stdio_config=StdioConfig(**self.stdio_config) if self.stdio_config else None,
            http_config=HttpConfig(**self.http_config) if self.http_config else None,
            enabled=self.enabled,
            health_status=ServerHealthStatus(self.health_status),
            last_connected_at=self.last_connected_at,
            last_health_check_at=self.last_health_check_at,
            discovered_tool_count=self.discovered_tool_count,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, entity: ServerEntity) -> "ServerModel":
        """Convert domain entity to database model."""
        return cls(
            id=str(entity.id),
            name=entity.name,
            description=entity.description,
            transport=entity.transport.value
            if hasattr(entity.transport, "value")
            else str(entity.transport),
            stdio_config=entity.stdio_config.model_dump() if entity.stdio_config else None,
            http_config=entity.http_config.model_dump() if entity.http_config else None,
            enabled=entity.enabled,
            health_status=entity.health_status.value
            if hasattr(entity.health_status, "value")
            else str(entity.health_status),
            last_connected_at=entity.last_connected_at,
            last_health_check_at=entity.last_health_check_at,
            discovered_tool_count=entity.discovered_tool_count,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
