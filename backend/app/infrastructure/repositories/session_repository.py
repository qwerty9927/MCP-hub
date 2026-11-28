"""Repository for MCP Session persistence and queries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Interval, and_, case, distinct, func, or_, select, update

import app.infrastructure.database as db_module
from app.core.enums.session_enum import SessionStatus
from app.domain.session_entity import SessionDetailEntity, SessionEntity
from app.infrastructure.database import Database
from app.models.execution_model import ExecutionModel
from app.models.session_model import SessionModel


class SessionRepositoryAbstract(ABC):
    """Abstract repository for MCP client session records."""

    @abstractmethod
    async def create(self, session: SessionEntity) -> SessionEntity:
        """Create a new session record."""
        pass

    @abstractmethod
    async def find_active_by_fingerprint(self, user_id: UUID, fingerprint: str) -> SessionEntity | None:
        """Return the owner's most recently active `active` session with this client fingerprint."""
        pass

    @abstractmethod
    async def get_by_id(self, session_id: UUID, *, user_id: UUID) -> SessionDetailEntity | None:
        """Retrieve detailed session view by ID including aggregated metrics."""
        pass

    @abstractmethod
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
        *,
        user_id: UUID,
    ) -> tuple[list[SessionEntity], int]:
        """List sessions with pagination, search, and status filtering."""
        pass

    @abstractmethod
    async def update_status(self, session_id: UUID, status: SessionStatus | str, *, user_id: UUID) -> bool:
        """Update session lifecycle status (only the owner's session when `user_id` is given)."""
        pass

    @abstractmethod
    async def update_activity(self, session_id: UUID, timestamp: datetime | None = None) -> None:
        """Update session last activity timestamp."""
        pass

    @abstractmethod
    async def complete_idle_sessions(self, now: datetime, default_idle_seconds: int) -> int:
        """Mark `completed` every active Session idle longer than its own timeout (else the default); returns how many.

        Leaves `last_activity_at` as it was, so it still says when the agent last acted.
        """
        pass


class PostgresSessionRepository(SessionRepositoryAbstract):
    """PostgreSQL implementation of SessionRepositoryAbstract."""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database or db_module.database

    async def create(self, session: SessionEntity) -> SessionEntity:
        async with self._database.session() as database_session:
            model = SessionModel.from_domain(session)
            database_session.add(model)
            await database_session.commit()
            await database_session.refresh(model)
            return model.to_domain()

    async def find_active_by_fingerprint(self, user_id: UUID, fingerprint: str) -> SessionEntity | None:
        async with self._database.session() as database_session:
            stmt = (
                select(SessionModel)
                .where(
                    SessionModel.user_id == str(user_id),
                    SessionModel.client_fingerprint == fingerprint,
                    SessionModel.status == SessionStatus.ACTIVE.value,
                )
                .order_by(SessionModel.last_activity_at.desc())
                .limit(1)
            )
            model = (await database_session.execute(stmt)).scalars().first()
            return model.to_domain() if model else None

    async def get_by_id(self, session_id: UUID, *, user_id: UUID) -> SessionDetailEntity | None:
        async with self._database.session() as database_session:
            owner_clause = SessionModel.user_id == str(user_id)
            stmt = (
                select(
                    SessionModel,
                    func.count(ExecutionModel.id).label("total_tool_calls"),
                    func.count(
                        case(
                            (ExecutionModel.status == "completed", 1),
                            (
                                and_(
                                    ExecutionModel.status.is_(None),
                                    ExecutionModel.is_error.is_(False),
                                ),
                                1,
                            ),
                            else_=None,
                        )
                    ).label("successful_tool_calls"),
                    func.count(
                        case(
                            (ExecutionModel.status == "failed", 1),
                            (
                                and_(
                                    ExecutionModel.status.is_(None),
                                    ExecutionModel.is_error.is_(True),
                                ),
                                1,
                            ),
                            else_=None,
                        )
                    ).label("failed_tool_calls"),
                    func.count(case((ExecutionModel.status == "rejected", 1), else_=None)).label("rejected_tool_calls"),
                )
                .outerjoin(ExecutionModel, ExecutionModel.session_id == SessionModel.id)
                .where(SessionModel.id == str(session_id), owner_clause)
                .group_by(SessionModel.id)
            )
            result = await database_session.execute(stmt)
            row = result.first()
            if not row:
                return None

            model, total, successful, failed, rejected = row
            status_value = SessionStatus(model.status) if model.status in SessionStatus._value2member_map_ else SessionStatus.ACTIVE
            return SessionDetailEntity(
                id=UUID(model.id),
                status=status_value,
                title=model.title,
                metadata=model.metadata_json,
                created_at=model.created_at,
                last_activity_at=model.last_activity_at,
                total_tool_calls=total,
                successful_tool_calls=successful,
                failed_tool_calls=failed,
                rejected_tool_calls=rejected,
            )

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
        *,
        user_id: UUID,
    ) -> tuple[list[SessionEntity], int]:
        async with self._database.session() as database_session:
            conditions = [SessionModel.user_id == str(user_id)]
            if search:
                search_term = f"%{search}%"
                conditions.append(
                    or_(
                        SessionModel.id.ilike(search_term),
                        SessionModel.title.ilike(search_term),
                    )
                )
            if status:
                conditions.append(func.lower(SessionModel.status) == status.lower())

            where_clause = and_(*conditions) if conditions else True

            # Count query
            count_stmt = select(func.count(distinct(SessionModel.id))).where(where_clause)
            total = (await database_session.execute(count_stmt)).scalar_one()

            # Items query with aggregated tool call counts
            stmt = (
                select(
                    SessionModel,
                    func.count(ExecutionModel.id).label("total_tool_calls"),
                )
                .outerjoin(ExecutionModel, ExecutionModel.session_id == SessionModel.id)
                .where(where_clause)
                .group_by(SessionModel.id)
                .order_by(SessionModel.last_activity_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await database_session.execute(stmt)
            rows = result.all()

            entities = [model.to_domain(total_tool_calls=count) for model, count in rows]
            return entities, total

    async def update_status(self, session_id: UUID, status: SessionStatus | str, *, user_id: UUID) -> bool:
        status_value = status.value if hasattr(status, "value") else str(status)
        async with self._database.session() as database_session:
            stmt = update(SessionModel).where(SessionModel.id == str(session_id))
            stmt = stmt.where(SessionModel.user_id == str(user_id))
            stmt = stmt.values(status=status_value, last_activity_at=datetime.now(UTC))
            result = await database_session.execute(stmt)
            await database_session.commit()
            return result.rowcount > 0

    async def update_activity(self, session_id: UUID, timestamp: datetime | None = None) -> None:
        now = timestamp or datetime.now(UTC)
        async with self._database.session() as database_session:
            stmt = update(SessionModel).where(SessionModel.id == str(session_id)).values(last_activity_at=now)
            await database_session.execute(stmt)
            await database_session.commit()

    async def complete_idle_sessions(self, now: datetime, default_idle_seconds: int) -> int:
        # One idempotent statement, so several hub instances can each run the job without a lock.
        idle_timeout = func.make_interval(
            0, 0, 0, 0, 0, 0, func.coalesce(SessionModel.idle_timeout_seconds, default_idle_seconds), type_=Interval
        )
        async with self._database.session() as database_session:
            stmt = (
                update(SessionModel)
                .where(
                    SessionModel.status == SessionStatus.ACTIVE.value,
                    SessionModel.last_activity_at + idle_timeout < now,
                )
                .values(status=SessionStatus.COMPLETED.value)
                .execution_options(synchronize_session=False)
            )

            result = await database_session.execute(stmt)
            await database_session.commit()

            return result.rowcount
