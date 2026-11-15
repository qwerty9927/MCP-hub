"""User repository interface and PostgreSQL implementation."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import app.infrastructure.database as db_module
from app.core.exceptions import ConflictError
from app.domain.user_entity import UserEntity
from app.models.user_model import UserModel


class UserRepositoryAbstract(ABC):
    """Persistence operations for accounts."""

    @abstractmethod
    async def create(self, user: UserEntity) -> UserEntity:
        """Persist a new account; raises ConflictError when the email is taken."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> UserEntity | None:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> UserEntity | None:
        pass


class PostgresUserRepository(UserRepositoryAbstract):
    async def create(self, user: UserEntity) -> UserEntity:
        async with db_module.async_session_factory() as session:
            model = UserModel.from_domain(user)
            session.add(model)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ConflictError("An account with this email already exists", details={"email": user.email}) from exc
            await session.refresh(model)
            return model.to_domain()

    async def get_by_id(self, user_id: UUID) -> UserEntity | None:
        async with db_module.async_session_factory() as session:
            result = await session.execute(select(UserModel).where(UserModel.id == str(user_id)))
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def get_by_email(self, email: str) -> UserEntity | None:
        async with db_module.async_session_factory() as session:
            result = await session.execute(select(UserModel).where(UserModel.email == email))
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None
