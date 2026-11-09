"""Repository for MCP Session persistence and queries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, case, distinct, func, or_, select, true, update

import app.infrastructure.database as db_module
from app.core.enums.session_enum import SessionStatus
from app.domain.session_entity import SessionDetailEntity, SessionEntity
from app.models.execution_model import ExecutionModel
from app.models.session_model import SessionModel


class SessionRepositoryAbstract(ABC):
    """Abstract repository for MCP client session records."""

    @abstractmethod
    async def init(
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
    async def list_by_query(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
    ) -> tuple[list[SessionEntity], int]:
        """List sessions with pagination, search, and status filtering."""
        pass

    @abstractmethod
    async def update_status(self, session_id: str, status: str) -> bool:
        """Update session lifecycle status."""
        pass


class PostgresSessionRepository(SessionRepositoryAbstract):
    """PostgreSQL implementation of SessionRepositoryAbstract."""

    async def init(
        self,
        session_id: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionEntity:
        async with db_module.async_session_factory() as db_session:
            stmt = select(SessionModel).where(SessionModel.id == session_id)
            found_session = (await db_session.execute(stmt)).scalar_one_or_none()

            if found_session is None:
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

                return new_session.to_domain()

            return found_session.to_domain()

    async def get_by_id(self, session_id: str) -> SessionDetailEntity | None:
        async with db_module.async_session_factory() as db_session:
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
                )
                .outerjoin(ExecutionModel, ExecutionModel.session_id == SessionModel.id)
                .where(SessionModel.id == session_id)
            )
            result = (await db_session.execute(stmt)).first()
            if not result:
                return None

            session, total, successful, failed = result
            status_val = SessionStatus(session.status) if session.status in SessionStatus._value2member_map_ else SessionStatus.ACTIVE
            return SessionDetailEntity(
                id=session.id,
                status=status_val,
                title=session.title,
                metadata=session.metadata_json,
                created_at=session.created_at,
                last_activity_at=session.last_activity_at,
                total_tool_calls=total,
                successful_tool_calls=successful,
                failed_tool_calls=failed,
            )

    async def list_by_query(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
    ) -> tuple[list[SessionEntity], int]:
        async with db_module.async_session_factory() as db_session:
            conditions = []
            if search:
                search_term = f"%{search}%".lower()
                conditions.append(
                    or_(
                        func.lower(SessionModel.id) == search_term,
                        SessionModel.title.ilike(search_term),
                    )
                )
            if status:
                conditions.append(func.lower(SessionModel.status) == status.lower())

            where_clause = and_(*conditions) if conditions else true

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
                .order_by(SessionModel.last_activity_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            rows = (await db_session.execute(stmt)).all()

            entities = [model.to_domain(total_tool_calls=count) for model, count in rows]
            return entities, total

    async def update_status(self, session_id: str, status: str) -> bool:
        async with db_module.async_session_factory() as db_session:
            stmt = update(SessionModel).where(SessionModel.id == session_id).values(status=status, last_activity_at=datetime.now(UTC))
            await db_session.execute(stmt)
            await db_session.commit()

            return True
