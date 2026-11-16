"""SQLAlchemy model for discovered MCP tools."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.domain.tool_entity import ToolEntity
from app.models.base_model import Base


class ToolModel(Base):
    """Database representation of a discovered tool from an MCP server."""

    __tablename__ = "discovered_tools"
    # A server lists each tool name once.
    __table_args__ = (
        UniqueConstraint("server_id", "name", name="uq_discovered_tools_server_name"),
        Index(
            "ix_discovered_tools_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))
    server_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    server_name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    availability_status: Mapped[str] = mapped_column(String(20), default="AVAILABLE", index=True, nullable=False)
    last_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    # Unit vector of tool_embedding_text(tool), searched by cosine distance (ADR-0006). NULL until embedded.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().EMBEDDING_DIMENSION), nullable=True)

    # Relationship to parent server
    server = relationship("ServerModel", back_populates="tools")

    def to_domain(self) -> ToolEntity:
        """Convert database model to domain entity."""
        return ToolEntity(
            id=UUID(self.id),
            server_id=UUID(self.server_id),
            server_name=self.server_name,
            user_id=UUID(self.user_id),
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
            id=str(entity.id),
            server_id=str(entity.server_id),
            server_name=entity.server_name,
            user_id=str(entity.user_id),
            name=entity.name,
            description=entity.description,
            input_schema=entity.input_schema or {},
            availability_status=entity.availability_status,
            last_discovered_at=entity.last_discovered_at,
        )
