"""Repository for Tool Execution history and session tool call queries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, asc, desc, func, or_, select

import app.infrastructure.database as db_module
from app.domain.execution_entity import ExecutionEntity, ToolUsageEntity
from app.domain.session_entity import ToolCallEntity
from app.models.execution_model import ExecutionModel


class ExecutionRepositoryAbstract(ABC):
    """Abstract repository for tool execution logs."""

    @abstractmethod
    async def create(self, execution: ExecutionEntity) -> ExecutionEntity:
        """Log a new tool execution record."""
        pass

    @abstractmethod
    async def get_by_id(self, execution_id: UUID, *, user_id: UUID) -> ExecutionEntity | None:
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
        *,
        user_id: UUID,
    ) -> tuple[list[ExecutionEntity], int]:
        """List executions with pagination and filtering."""
        pass

    @abstractmethod
    async def list_by_session(
        self,
        session_id: UUID,
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
    async def get_tool_call(self, session_id: UUID, call_id: UUID) -> ToolCallEntity | None:
        """Retrieve a specific tool call within a session."""
        pass

    @abstractmethod
    async def tool_usage(self, *, user_id: UUID, since: datetime | None, limit: int) -> tuple[list[ToolUsageEntity], int]:
        """The owner's most-called Tools since `since` (all time if None), most first, and the total calls in that period."""
        pass


class PostgresExecutionRepository(ExecutionRepositoryAbstract):
    """PostgreSQL implementation of ExecutionRepositoryAbstract using SQLAlchemy."""

    async def create(self, execution: ExecutionEntity) -> ExecutionEntity:
        async with db_module.async_session_factory() as session:
            model = ExecutionModel.from_domain(execution)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model.to_domain()

    async def get_by_id(self, execution_id: UUID, *, user_id: UUID) -> ExecutionEntity | None:
        async with db_module.async_session_factory() as session:
            stmt = _owned(select(ExecutionModel).where(ExecutionModel.id == str(execution_id)), user_id)
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
        *,
        user_id: UUID,
    ) -> tuple[list[ExecutionEntity], int]:
        async with db_module.async_session_factory() as session:
            stmt = _owned(select(ExecutionModel), user_id)

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
            return [model.to_domain() for model in models], total

    async def list_by_session(
        self,
        session_id: UUID,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        order: str = "asc",
        status: str | None = None,
        server_name: str | None = None,
        tool_name: str | None = None,
    ) -> tuple[list[ToolCallEntity], int]:
        async with db_module.async_session_factory() as session:
            conditions = [ExecutionModel.session_id == str(session_id)]

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
            return [model.to_tool_call_domain() for model in models], total

    async def get_tool_call(self, session_id: UUID, call_id: UUID) -> ToolCallEntity | None:
        async with db_module.async_session_factory() as session:
            stmt = select(ExecutionModel).where(
                and_(
                    ExecutionModel.id == str(call_id),
                    ExecutionModel.session_id == str(session_id),
                )
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return model.to_tool_call_domain() if model else None

    async def tool_usage(self, *, user_id: UUID, since: datetime | None, limit: int) -> tuple[list[ToolUsageEntity], int]:
        async with db_module.async_session_factory() as session:
            in_period = _owned(select(ExecutionModel), user_id)
            if since is not None:
                in_period = in_period.where(ExecutionModel.executed_at >= since)
            total = (await session.execute(select(func.count()).select_from(in_period.subquery()))).scalar_one()

            # A tool name can exist on several Servers, so usage is counted per (Server, Tool).
            status = func.lower(ExecutionModel.status)
            calls = func.count()
            stmt = (
                select(
                    ExecutionModel.server_id,
                    func.max(ExecutionModel.server_name),  # the latest name, should the Server have been renamed
                    ExecutionModel.tool_name,
                    calls,
                    func.count().filter(status == "completed"),
                    func.count().filter(status == "failed"),
                    func.count().filter(status == "rejected"),
                    func.avg(ExecutionModel.duration_ms).filter(status != "rejected"),
                    func.max(ExecutionModel.executed_at),
                )
                .where(in_period.whereclause)
                .group_by(ExecutionModel.server_id, ExecutionModel.tool_name)
                .order_by(calls.desc(), ExecutionModel.tool_name)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
            return [
                ToolUsageEntity(
                    server_id=UUID(server_id),
                    server_name=server_name,
                    tool_name=tool_name,
                    total_calls=total_calls,
                    completed_calls=completed,
                    failed_calls=failed,
                    rejected_calls=rejected,
                    avg_duration_ms=float(avg_duration) if avg_duration is not None else None,
                    last_called_at=last_called_at,
                )
                for server_id, server_name, tool_name, total_calls, completed, failed, rejected, avg_duration, last_called_at in rows
            ], total


def _owned(stmt: Select, user_id: UUID) -> Select:
    """Limit an Execution query to `user_id`'s Executions, including those whose Server was deleted."""
    return stmt.where(ExecutionModel.user_id == str(user_id))
