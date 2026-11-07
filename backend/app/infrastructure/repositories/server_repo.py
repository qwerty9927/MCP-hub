import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.infrastructure.database as db_module
from app.core.enums.server_enum import ServerHealthStatus, TransportType
from app.domain.server_entity import ServerEntity
from app.models.server_model import ServerModel


class ServerRepositoryAbstract(ABC):
    """Abstract repository for MCP Server entities."""

    @abstractmethod
    async def create(self, server: ServerEntity) -> ServerEntity:
        """Create a new server record."""
        pass

    @abstractmethod
    async def get_by_id(self, server_id: UUID) -> ServerEntity | None:
        """Retrieve server by ID."""
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> ServerEntity | None:
        """Retrieve server by unique name."""
        pass

    @abstractmethod
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        enabled: bool | None = None,
        transport: TransportType | None = None,
        health_status: ServerHealthStatus | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[ServerEntity], int]:
        """List servers with pagination, filtering, and sorting."""
        pass

    @abstractmethod
    async def update(self, server: ServerEntity) -> ServerEntity:
        """Update existing server record."""
        pass

    @abstractmethod
    async def delete(self, server_id: UUID) -> bool:
        """Delete server by ID."""
        pass


class PostgresServerRepository(ServerRepositoryAbstract):
    """PostgreSQL implementation of ServerRepositoryAbstract using SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker | None = None) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker:
        return self._session_factory or db_module.async_session_factory

    @session_factory.setter
    def session_factory(self, factory: async_sessionmaker | None) -> None:
        self._session_factory = factory

    async def create(self, server: ServerEntity) -> ServerEntity:
        async with self.session_factory() as session:
            model = ServerModel.from_domain(server)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model.to_domain()

    async def get_by_id(self, server_id: UUID) -> ServerEntity | None:
        async with self.session_factory() as session:
            stmt = select(ServerModel).where(ServerModel.id == str(server_id))
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def get_by_name(self, name: str) -> ServerEntity | None:
        async with self.session_factory() as session:
            stmt = select(ServerModel).where(func.lower(ServerModel.name) == name.lower())
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        enabled: bool | None = None,
        transport: TransportType | None = None,
        health_status: ServerHealthStatus | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[ServerEntity], int]:
        async with self.session_factory() as session:
            stmt = select(ServerModel)

            # Filtering
            if enabled is not None:
                stmt = stmt.where(ServerModel.enabled == enabled)
            if transport is not None:
                transport_val = transport.value if hasattr(transport, "value") else str(transport)
                stmt = stmt.where(ServerModel.transport == transport_val)
            if health_status is not None:
                health_val = (
                    health_status.value if hasattr(health_status, "value") else str(health_status)
                )
                stmt = stmt.where(ServerModel.health_status == health_val)
            if search:
                term = f"%{search.lower()}%"
                stmt = stmt.where(
                    func.lower(ServerModel.name).like(term)
                    | func.lower(ServerModel.description).like(term)
                )

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_result = await session.execute(count_stmt)
            total = total_result.scalar_one()

            # Sorting
            sort_column = getattr(ServerModel, sort_by, ServerModel.created_at)
            stmt = stmt.order_by(
                sort_column.desc() if sort_order.lower() == "desc" else sort_column.asc()
            )

            # Pagination
            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)

            result = await session.execute(stmt)
            models = result.scalars().all()
            return [m.to_domain() for m in models], total

    async def update(self, server: ServerEntity) -> ServerEntity:
        async with self.session_factory() as session:
            stmt = select(ServerModel).where(ServerModel.id == str(server.id))
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                model = ServerModel.from_domain(server)
                session.add(model)
            else:
                model.name = server.name
                model.description = server.description
                model.transport = (
                    server.transport.value
                    if hasattr(server.transport, "value")
                    else str(server.transport)
                )
                model.stdio_config = (
                    server.stdio_config.model_dump() if server.stdio_config else None
                )
                model.http_config = server.http_config.model_dump() if server.http_config else None
                model.enabled = server.enabled
                model.health_status = (
                    server.health_status.value
                    if hasattr(server.health_status, "value")
                    else str(server.health_status)
                )
                model.last_connected_at = server.last_connected_at
                model.last_health_check_at = server.last_health_check_at
                model.discovered_tool_count = server.discovered_tool_count
                model.updated_at = server.updated_at

            await session.commit()
            await session.refresh(model)
            return model.to_domain()

    async def delete(self, server_id: UUID) -> bool:
        async with self.session_factory() as session:
            stmt = select(ServerModel).where(ServerModel.id == str(server_id))
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                await session.delete(model)
                await session.commit()
                return True
            return False


class InMemoryServerRepository(ServerRepositoryAbstract):
    """In-memory implementation of ServerRepositoryAbstract."""

    def __init__(self) -> None:
        self._servers: dict[UUID, ServerEntity] = {}
        self._lock = asyncio.Lock()

    async def create(self, server: ServerEntity) -> ServerEntity:
        async with self._lock:
            self._servers[server.id] = server
            return server

    async def get_by_id(self, server_id: UUID) -> ServerEntity | None:
        async with self._lock:
            return self._servers.get(server_id)

    async def get_by_name(self, name: str) -> ServerEntity | None:
        async with self._lock:
            for s in self._servers.values():
                if s.name.lower() == name.lower():
                    return s
            return None

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        enabled: bool | None = None,
        transport: TransportType | None = None,
        health_status: ServerHealthStatus | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[ServerEntity], int]:
        async with self._lock:
            items = list(self._servers.values())

        # Filtering
        if enabled is not None:
            items = [s for s in items if s.enabled == enabled]
        if transport is not None:
            items = [s for s in items if s.transport == transport]
        if health_status is not None:
            items = [s for s in items if s.health_status == health_status]
        if search:
            q = search.lower()
            items = [
                s
                for s in items
                if q in s.name.lower() or (s.description and q in s.description.lower())
            ]

        # Sorting
        reverse = sort_order.lower() == "desc"
        if sort_by == "name":
            items.sort(key=lambda s: s.name.lower(), reverse=reverse)
        elif sort_by == "updated_at":
            items.sort(key=lambda s: s.updated_at, reverse=reverse)
        elif sort_by == "discovered_tool_count":
            items.sort(key=lambda s: s.discovered_tool_count, reverse=reverse)
        else:  # default created_at
            items.sort(key=lambda s: s.created_at, reverse=reverse)

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end], total

    async def update(self, server: ServerEntity) -> ServerEntity:
        async with self._lock:
            server.updated_at = datetime.now(UTC)
            self._servers[server.id] = server
            return server

    async def delete(self, server_id: UUID) -> bool:
        async with self._lock:
            if server_id in self._servers:
                del self._servers[server_id]
                return True
            return False
