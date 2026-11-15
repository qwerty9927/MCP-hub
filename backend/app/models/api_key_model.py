"""API key ORM model. Only a SHA-256 hash of the key is stored."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.api_key_entity import ApiKeyEntity
from app.models.base_model import Base


class ApiKeyModel(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_idle_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def to_domain(self) -> ApiKeyEntity:
        return ApiKeyEntity(
            id=UUID(self.id),
            user_id=UUID(self.user_id),
            name=self.name,
            key_prefix=self.key_prefix,
            key_hash=self.key_hash,
            created_at=self.created_at,
            last_used_at=self.last_used_at,
            revoked_at=self.revoked_at,
            session_idle_minutes=self.session_idle_minutes,
        )

    @classmethod
    def from_domain(cls, entity: ApiKeyEntity) -> "ApiKeyModel":
        return cls(
            id=str(entity.id),
            user_id=str(entity.user_id),
            name=entity.name,
            key_prefix=entity.key_prefix,
            key_hash=entity.key_hash,
            created_at=entity.created_at,
            last_used_at=entity.last_used_at,
            revoked_at=entity.revoked_at,
            session_idle_minutes=entity.session_idle_minutes,
        )
