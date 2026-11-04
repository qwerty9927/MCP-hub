import asyncio
from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.infrastructure.database as db_module
from app.domain.execution_entity import ExecutionEntity
from app.models.execution_model import ExecutionModel


class ExecutionRepositoryAbstract(ABC):
    """Abstract repository for tool execution logs."""

    @abstractmethod
    async def create(self, execution: ExecutionEntity) -> ExecutionEntity:
        """Log a new tool execution record."""
        pass

    @abstractmethod
    async def get_by_id(self, execution_id: UUID) -> ExecutionEntity | None:
        """Retrieve an execution record by ID."""
        pass

    @abstractmethod
    async def list(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        is_error: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExecutionEntity], int]:
        """List executions with pagination and filtering."""
        pass


class PostgresExecutionRepository(ExecutionRepositoryAbstract):
    """PostgreSQL implementation of ExecutionRepositoryAbstract using SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker | None = None) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker:
        return self._session_factory or db_module.async_session_factory

    @session_factory.setter
    def session_factory(self, factory: async_sessionmaker | None) -> None:
        self._session_factory = factory

    async def create(self, execution: ExecutionEntity) -> ExecutionEntity:
        async with self.session_factory() as session:
            model = ExecutionModel.from_domain(execution)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model.to_domain()

    async def get_by_id(self, execution_id: UUID) -> ExecutionEntity | None:
        async with self.session_factory() as session:
            stmt = select(ExecutionModel).where(ExecutionModel.id == str(execution_id))
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        is_error: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExecutionEntity], int]:
        async with self.session_factory() as session:
            stmt = select(ExecutionModel)

            if server_id is not None:
                stmt = stmt.where(ExecutionModel.server_id == str(server_id))
            if tool_name is not None:
                stmt = stmt.where(func.lower(ExecutionModel.tool_name) == tool_name.lower())
            if is_error is not None:
                stmt = stmt.where(ExecutionModel.is_error == is_error)

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar_one()

            # Order latest first
            stmt = stmt.order_by(ExecutionModel.executed_at.desc())

            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)

            result = await session.execute(stmt)
            models = result.scalars().all()
            return [m.to_domain() for m in models], total


class InMemoryExecutionRepository(ExecutionRepositoryAbstract):
    """In-memory implementation of ExecutionRepositoryAbstract."""

    def __init__(self) -> None:
        self._executions: dict[UUID, ExecutionEntity] = {}
        self._lock = asyncio.Lock()

    async def create(self, execution: ExecutionEntity) -> ExecutionEntity:
        async with self._lock:
            self._executions[execution.id] = execution
            return execution

    async def get_by_id(self, execution_id: UUID) -> ExecutionEntity | None:
        async with self._lock:
            return self._executions.get(execution_id)

    async def list(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        is_error: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExecutionEntity], int]:
        async with self._lock:
            items = list(self._executions.values())

        if server_id is not None:
            items = [e for e in items if e.server_id == server_id]
        if tool_name is not None:
            items = [e for e in items if e.tool_name.lower() == tool_name.lower()]
        if is_error is not None:
            items = [e for e in items if e.is_error == is_error]

        # Sort latest first
        items.sort(key=lambda e: e.executed_at, reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end], total
