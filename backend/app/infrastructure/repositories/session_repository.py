"""Repository for MCP Session persistence and queries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, case, distinct, func, or_, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.infrastructure.database as db_module
from app.core.enums.session_enum import SessionStatus
from app.domain.session_entity import SessionDetailEntity, SessionEntity
from app.models.execution_model import ExecutionModel
from app.models.session_model import SessionModel


class SessionRepositoryAbstract(ABC):
    """Abstract repository for MCP client session records."""

    @abstractmethod
    async def create(self, session: SessionEntity) -> SessionEntity:
        """Create a new session record."""
        pass

    @abstractmethod
    async def get_or_create(
        self,
        session_id: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionEntity:
        """Get an existing session by ID or create a new one."""
        pass

    @abstractmethod
    async def get_by_id(self, session_id: str) -> SessionDetailEntity | None:
        """Retrieve detailed session view by ID including aggregated metrics."""
        pass

    @abstractmethod
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
    ) -> tuple[list[SessionEntity], int]:
        """List sessions with pagination, search, and status filtering."""
        pass

    @abstractmethod
    async def update_status(self, session_id: str, status: SessionStatus | str) -> bool:
        """Update session lifecycle status."""
        pass

    @abstractmethod
    async def update_activity(self, session_id: str, timestamp: datetime | None = None) -> None:
        """Update session last activity timestamp."""
        pass


class PostgresSessionRepository(SessionRepositoryAbstract):
    """PostgreSQL implementation of SessionRepositoryAbstract."""

    def __init__(self, session_factory: async_sessionmaker | None = None) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker:
        return self._session_factory or db_module.async_session_factory

    @session_factory.setter
    def session_factory(self, factory: async_sessionmaker | None) -> None:
        self._session_factory = factory

    async def create(self, session: SessionEntity) -> SessionEntity:
        async with self.session_factory() as db_session:
            model = SessionModel.from_domain(session)
            db_session.add(model)
            await db_session.commit()
            await db_session.refresh(model)
            return model.to_domain()

    async def get_or_create(
        self,
        session_id: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionEntity:
        async with self.session_factory() as db_session:
            stmt = select(SessionModel).where(SessionModel.id == session_id)
            result = await db_session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                # Update title/metadata if provided and not set
                updated = False
                if title and not model.title:
                    model.title = title
                    updated = True
                if metadata and not model.metadata_json:
                    model.metadata_json = metadata
                    updated = True
                if updated:
                    await db_session.commit()
                    await db_session.refresh(model)
                return model.to_domain()

            # Create new session
            now = datetime.now(UTC)
            new_session = SessionModel(
                id=session_id,
                title=title or f"Session {session_id[:8]}",
                status="active",
                metadata_json=metadata,
                created_at=now,
                last_activity_at=now,
            )
            db_session.add(new_session)
            await db_session.commit()
            await db_session.refresh(new_session)
            return new_session.to_domain()

    async def get_by_id(self, session_id: str) -> SessionDetailEntity | None:
        async with self.session_factory() as db_session:
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
                .where(SessionModel.id == session_id)
                .group_by(SessionModel.id)
            )
            result = await db_session.execute(stmt)
            row = result.first()
            if not row:
                return None

            model, total, successful, failed, rejected = row
            status_val = SessionStatus(model.status) if model.status in SessionStatus._value2member_map_ else SessionStatus.ACTIVE
            return SessionDetailEntity(
                id=model.id,
                status=status_val,
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
    ) -> tuple[list[SessionEntity], int]:
        async with self.session_factory() as db_session:
            conditions = []
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
            total = (await db_session.execute(count_stmt)).scalar_one()

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
            result = await db_session.execute(stmt)
            rows = result.all()

            entities = [model.to_domain(total_tool_calls=count) for model, count in rows]
            return entities, total

    async def update_status(self, session_id: str, status: SessionStatus | str) -> bool:
        status_val = status.value if hasattr(status, "value") else str(status)
        async with self.session_factory() as db_session:
            stmt = update(SessionModel).where(SessionModel.id == session_id).values(status=status_val, last_activity_at=datetime.now(UTC))
            result = await db_session.execute(stmt)
            await db_session.commit()
            return result.rowcount > 0

    async def update_activity(self, session_id: str, timestamp: datetime | None = None) -> None:
        now = timestamp or datetime.now(UTC)
        async with self.session_factory() as db_session:
            stmt = update(SessionModel).where(SessionModel.id == session_id).values(last_activity_at=now)
            await db_session.execute(stmt)
            await db_session.commit()
