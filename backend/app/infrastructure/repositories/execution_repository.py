"""Repository for Tool Execution history and session tool call queries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.infrastructure.database as db_module
from app.domain.execution_entity import ExecutionEntity
from app.domain.session_entity import ToolCallEntity
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
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExecutionEntity], int]:
        """List executions with pagination and filtering."""
        pass

    @abstractmethod
    async def list_by_session(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        order: str = "asc",
        status: str | None = None,
        server_name: str | None = None,
        tool_name: str | None = None,
    ) -> tuple[list[ToolCallEntity], int]:
        """Retrieve tool calls belonging to a session with pagination, sorting, and filters."""
        pass

    @abstractmethod
    async def get_tool_call(self, session_id: str, call_id: UUID) -> ToolCallEntity | None:
        """Retrieve a specific tool call within a session."""
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
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExecutionEntity], int]:
        async with self.session_factory() as session:
            stmt = select(ExecutionModel)

            if server_id is not None:
                stmt = stmt.where(ExecutionModel.server_id == str(server_id))
            if tool_name is not None:
                stmt = stmt.where(ExecutionModel.tool_name.ilike(f"%{tool_name}%"))
            if is_error is not None:
                stmt = stmt.where(ExecutionModel.is_error == is_error)
            if status:
                stmt = stmt.where(func.lower(ExecutionModel.status) == status.strip().lower())

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

    async def list_by_session(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        order: str = "asc",
        status: str | None = None,
        server_name: str | None = None,
        tool_name: str | None = None,
    ) -> tuple[list[ToolCallEntity], int]:
        async with self.session_factory() as session:
            conditions = [ExecutionModel.session_id == session_id]

            if status:
                status_clean = status.strip().lower()
                if status_clean == "running":
                    conditions.append(ExecutionModel.status == "running")
                elif status_clean == "completed":
                    conditions.append(
                        or_(
                            ExecutionModel.status == "completed",
                            and_(
                                ExecutionModel.status.is_(None),
                                ExecutionModel.is_error.is_(False),
                            ),
                        )
                    )
                elif status_clean == "failed":
                    conditions.append(
                        or_(
                            ExecutionModel.status == "failed",
                            and_(
                                ExecutionModel.status.is_(None),
                                ExecutionModel.is_error.is_(True),
                            ),
                        )
                    )
                else:
                    conditions.append(func.lower(ExecutionModel.status) == status_clean)

            if server_name:
                conditions.append(ExecutionModel.server_name.ilike(f"%{server_name}%"))

            if tool_name:
                conditions.append(ExecutionModel.tool_name.ilike(f"%{tool_name}%"))

            where_clause = and_(*conditions)

            # Count total matching query
            count_stmt = select(func.count(ExecutionModel.id)).where(where_clause)
            total = (await session.execute(count_stmt)).scalar_one()

            # Determine sorting column
            sort_field = sort_by.strip().lower() if sort_by else "created_at"
            if sort_field in ("started_at", "created_at", "executed_at"):
                col = func.coalesce(ExecutionModel.started_at, ExecutionModel.executed_at)
            elif sort_field == "completed_at":
                col = ExecutionModel.completed_at
            elif sort_field in ("duration", "duration_ms"):
                col = ExecutionModel.duration_ms
            elif sort_field == "server_name":
                col = ExecutionModel.server_name
            elif sort_field == "tool_name":
                col = ExecutionModel.tool_name
            elif sort_field == "status":
                col = ExecutionModel.status
            else:
                col = func.coalesce(ExecutionModel.started_at, ExecutionModel.executed_at)

            # Sort direction
            order_clean = order.strip().lower() if order else "asc"
            order_clause = desc(col) if order_clean == "desc" else asc(col)

            stmt = select(ExecutionModel).where(where_clause).order_by(order_clause).offset((page - 1) * page_size).limit(page_size)

            result = await session.execute(stmt)
            models = result.scalars().all()
            return [m.to_tool_call_domain() for m in models], total

    async def get_tool_call(self, session_id: str, call_id: UUID) -> ToolCallEntity | None:
        async with self.session_factory() as session:
            stmt = select(ExecutionModel).where(
                and_(
                    ExecutionModel.id == str(call_id),
                    ExecutionModel.session_id == session_id,
                )
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return model.to_tool_call_domain() if model else None
