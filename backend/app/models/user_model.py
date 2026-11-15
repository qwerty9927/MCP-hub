"""User account ORM model."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.user_entity import UserEntity
from app.models.base_model import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    def to_domain(self) -> UserEntity:
        return UserEntity(
            id=UUID(self.id),
            email=self.email,
            password_hash=self.password_hash,
            created_at=self.created_at,
        )

    @classmethod
    def from_domain(cls, entity: UserEntity) -> "UserModel":
        return cls(
            id=str(entity.id),
            email=entity.email,
            password_hash=entity.password_hash,
            created_at=entity.created_at,
        )
