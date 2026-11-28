"""Repository for Tool Execution history and session tool call queries."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, asc, case, desc, func, or_, select

import app.infrastructure.database as db_module
from app.domain.execution_entity import CallBucketEntity, CallStatsEntity, ExecutionEntity, ToolUsageEntity
from app.domain.session_entity import ToolCallEntity
from app.infrastructure.database import Database
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
    async def tool_usage(
        self, *, user_id: UUID, since: datetime | None, limit: int, server_id: UUID | None = None
    ) -> tuple[list[ToolUsageEntity], int]:
        """The owner's most-called Tools since `since` (all time if None), most first, and the total calls in that period.
        With `server_id`, only that Server's Tools and calls."""
        pass

    @abstractmethod
    async def call_stats(
        self, *, user_id: UUID, since: datetime | None, until: datetime | None = None, server_id: UUID | None = None
    ) -> CallStatsEntity:
        """Totals over the owner's calls in [since, until) (open ends when None), optionally one Server's."""
        pass

    @abstractmethod
    async def call_timeseries(
        self, *, user_id: UUID, since: datetime, until: datetime, bucket: timedelta, server_id: UUID | None = None
    ) -> list[CallBucketEntity]:
        """The owner's calls counted per bucket from `since` to `until`, one entry per bucket, empty ones included."""
        pass

    @abstractmethod
    async def first_call_at(self, *, user_id: UUID, server_id: UUID | None = None) -> datetime | None:
        """When the owner's earliest recorded call happened, or None when there are none."""
        pass


class PostgresExecutionRepository(ExecutionRepositoryAbstract):
    """PostgreSQL implementation of ExecutionRepositoryAbstract using SQLAlchemy."""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database or db_module.database

    async def create(self, execution: ExecutionEntity) -> ExecutionEntity:
        async with self._database.session() as session:
            model = ExecutionModel.from_domain(execution)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model.to_domain()

    async def get_by_id(self, execution_id: UUID, *, user_id: UUID) -> ExecutionEntity | None:
        async with self._database.session() as session:
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
        async with self._database.session() as session:
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
        async with self._database.session() as session:
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
        async with self._database.session() as session:
            stmt = select(ExecutionModel).where(
                and_(
                    ExecutionModel.id == str(call_id),
                    ExecutionModel.session_id == str(session_id),
                )
            )
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return model.to_tool_call_domain() if model else None

    async def tool_usage(
        self, *, user_id: UUID, since: datetime | None, limit: int, server_id: UUID | None = None
    ) -> tuple[list[ToolUsageEntity], int]:
        async with self._database.session() as session:
            conditions = _period(user_id, since=since, until=None, server_id=server_id)
            total = (await session.execute(select(func.count()).select_from(ExecutionModel).where(*conditions))).scalar_one()

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
                    _p90_reached(),
                )
                .where(*conditions)
                .group_by(ExecutionModel.server_id, ExecutionModel.tool_name)
                .order_by(calls.desc(), ExecutionModel.tool_name)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
            return [
                ToolUsageEntity(
                    server_id=UUID(row_server_id),
                    server_name=server_name,
                    tool_name=tool_name,
                    total_calls=total_calls,
                    completed_calls=completed,
                    failed_calls=failed,
                    rejected_calls=rejected,
                    avg_duration_ms=_float(avg_duration),
                    last_called_at=last_called_at,
                    p90_duration_ms=_float(p90_duration),
                )
                for (
                    row_server_id,
                    server_name,
                    tool_name,
                    total_calls,
                    completed,
                    failed,
                    rejected,
                    avg_duration,
                    last_called_at,
                    p90_duration,
                ) in rows
            ], total

    async def call_stats(
        self, *, user_id: UUID, since: datetime | None, until: datetime | None = None, server_id: UUID | None = None
    ) -> CallStatsEntity:
        async with self._database.session() as session:
            status = func.lower(ExecutionModel.status)
            stmt = select(
                func.count(),
                func.count().filter(status == "completed"),
                func.count().filter(status == "failed"),
                func.count().filter(status == "rejected"),
                _p90_reached(),
            ).where(*_period(user_id, since=since, until=until, server_id=server_id))
            total, completed, failed, rejected, p90 = (await session.execute(stmt)).one()
            return CallStatsEntity(
                total_calls=total,
                completed_calls=completed,
                failed_calls=failed,
                rejected_calls=rejected,
                p90_duration_ms=_float(p90),
            )

    async def call_timeseries(
        self, *, user_id: UUID, since: datetime, until: datetime, bucket: timedelta, server_id: UUID | None = None
    ) -> list[CallBucketEntity]:
        async with self._database.session() as session:
            status = func.lower(ExecutionModel.status)
            # date_bin puts each call in the bucket since + k * bucket that contains it.
            start = func.date_bin(bucket, ExecutionModel.executed_at, since)
            stmt = (
                select(
                    start,
                    func.count(),
                    func.count().filter(status == "completed"),
                    func.count().filter(status == "failed"),
                    func.count().filter(status == "rejected"),
                )
                .where(*_period(user_id, since=since, until=until, server_id=server_id))
                .group_by(start)
            )
            rows = {row[0]: row[1:] for row in (await session.execute(stmt)).all()}

        count = max(1, math.ceil((until - since) / bucket))
        buckets = []
        for index in range(count):
            bucket_start = since + index * bucket
            total, completed, failed, rejected = rows.get(bucket_start, (0, 0, 0, 0))
            buckets.append(
                CallBucketEntity(
                    start=bucket_start,
                    total_calls=total,
                    completed_calls=completed,
                    failed_calls=failed,
                    rejected_calls=rejected,
                )
            )
        return buckets

    async def first_call_at(self, *, user_id: UUID, server_id: UUID | None = None) -> datetime | None:
        async with self._database.session() as session:
            stmt = select(func.min(ExecutionModel.executed_at)).where(*_period(user_id, since=None, until=None, server_id=server_id))
            return (await session.execute(stmt)).scalar_one()


def _owned(stmt: Select, user_id: UUID) -> Select:
    """Limit an Execution query to `user_id`'s Executions, including those whose Server was deleted."""
    return stmt.where(ExecutionModel.user_id == str(user_id))


def _period(user_id: UUID, *, since: datetime | None, until: datetime | None, server_id: UUID | None) -> list[ColumnElement[bool]]:
    """Conditions for the owner's Executions in [since, until), optionally one Server's."""
    conditions: list[ColumnElement[bool]] = [ExecutionModel.user_id == str(user_id)]
    if since is not None:
        conditions.append(ExecutionModel.executed_at >= since)
    if until is not None:
        conditions.append(ExecutionModel.executed_at < until)
    if server_id is not None:
        conditions.append(ExecutionModel.server_id == str(server_id))
    return conditions


def _p90_reached() -> ColumnElement[Any]:
    """90th-percentile duration of the calls that reached the Server; rejected ones (NULL here) are skipped."""
    reached = case((func.lower(ExecutionModel.status) != "rejected", ExecutionModel.duration_ms), else_=None)
    return func.percentile_cont(0.9).within_group(reached)


def _float(value: Any) -> float | None:
    return float(value) if value is not None else None
