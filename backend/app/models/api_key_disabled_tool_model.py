"""ORM model for tools hidden from one API key (ADR-0007).

Visibility is stored as exceptions: a row means "this key cannot see or run this tool". It is keyed by
server and tool name, not the tool's id, because a server's tools get new ids on every re-discovery.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import Base


class ApiKeyDisabledToolModel(Base):
    __tablename__ = "api_key_disabled_tools"

    api_key_id: Mapped[str] = mapped_column(String(36), ForeignKey("api_keys.id", ondelete="CASCADE"), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(36), ForeignKey("mcp_servers.id", ondelete="CASCADE"), primary_key=True)
    tool_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
