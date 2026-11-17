"""SQLAlchemy model for the OAuth credentials of one MCP server (ADR-0008)."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import Base


class ServerOAuthCredentialModel(Base):
    """The OAuth client registration and tokens the hub uses for one server. Secrets are Fernet-encrypted."""

    __tablename__ = "server_oauth_credentials"

    server_id: Mapped[str] = mapped_column(String(36), ForeignKey("mcp_servers.id", ondelete="CASCADE"), primary_key=True)
    client_info_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # OAuthClientInformationFull JSON
    tokens_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # OAuthToken JSON
    access_token_expires_at: Mapped[float | None] = mapped_column(Float, nullable=True)  # unix seconds
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
