"""Console refresh token ORM model (ADR-0009). Only a SHA-256 hash of the token is stored."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.refresh_token_entity import RefreshTokenEntity
from app.models.base_model import Base


class RefreshTokenModel(Base):
    __tablename__ = "console_refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> RefreshTokenEntity:
        return RefreshTokenEntity(
            id=UUID(self.id),
            user_id=UUID(self.user_id),
            family_id=UUID(self.family_id),
            token_hash=self.token_hash,
            created_at=self.created_at,
            expires_at=self.expires_at,
            used_at=self.used_at,
            revoked_at=self.revoked_at,
        )

    @classmethod
    def from_domain(cls, entity: RefreshTokenEntity) -> "RefreshTokenModel":
        return cls(
            id=str(entity.id),
            user_id=str(entity.user_id),
            family_id=str(entity.family_id),
            token_hash=entity.token_hash,
            created_at=entity.created_at,
            expires_at=entity.expires_at,
            used_at=entity.used_at,
            revoked_at=entity.revoked_at,
        )
