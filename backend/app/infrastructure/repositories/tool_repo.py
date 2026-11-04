import asyncio
from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.tool_entity import ToolEntity
from app.infrastructure.database import async_session_factory
from app.models.tool_model import ToolModel


class ToolRepositoryAbstract(ABC):
    """Abstract repository for discovered tool metadata persistence."""

    @abstractmethod
    async def save_server_tools(
        self,
        server_id: UUID,
        server_name: str,
        tools: list[ToolEntity],
    ) -> list[ToolEntity]:
        """Atomically persist or replace tools discovered for a server."""
        pass

    @abstractmethod
    async def delete_server_tools(self, server_id: UUID) -> None:
        """Delete all cached tools for a specific server."""
        pass

    @abstractmethod
    async def get_tool(
        self,
        tool_id_or_name: str,
        server_id: UUID | None = None,
    ) -> ToolEntity | None:
        """Retrieve a tool by qualified ID or tool name."""
        pass

    @abstractmethod
    async def list_tools(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ToolEntity], int]:
        """List and search tools across servers with pagination."""
        pass

    @abstractmethod
    async def load_all_tools(self) -> list[ToolEntity]:
        """Load all discovered tools from persistent storage."""
        pass


class SqliteToolRepository(ToolRepositoryAbstract):
    """SQLite implementation of ToolRepositoryAbstract using SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker | None = None) -> None:
        self.session_factory = session_factory or async_session_factory

    async def save_server_tools(
        self,
        server_id: UUID,
        server_name: str,
        tools: list[ToolEntity],
    ) -> list[ToolEntity]:
        async with self.session_factory() as session:
            # Delete existing tools for this server
            await session.execute(delete(ToolModel).where(ToolModel.server_id == str(server_id)))

            saved_entities: list[ToolEntity] = []
            for tool in tools:
                model = ToolModel(
                    id=tool.id,
                    server_id=str(server_id),
                    server_name=server_name,
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema or {},
                    availability_status=tool.availability_status,
                    last_discovered_at=tool.last_discovered_at,
                )
                session.add(model)
                saved_entities.append(tool)

            await session.commit()
            return saved_entities

    async def delete_server_tools(self, server_id: UUID) -> None:
        async with self.session_factory() as session:
            await session.execute(delete(ToolModel).where(ToolModel.server_id == str(server_id)))
            await session.commit()

    async def get_tool(
        self,
        tool_id_or_name: str,
        server_id: UUID | None = None,
    ) -> ToolEntity | None:
        async with self.session_factory() as session:
            # 1. Look up by exact qualified ID
            stmt = select(ToolModel).where(ToolModel.id == tool_id_or_name)
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            if model:
                return model.to_domain()

            # 2. Look up by name and server_id if given
            if server_id is not None:
                stmt = select(ToolModel).where(
                    ToolModel.server_id == str(server_id),
                    func.lower(ToolModel.name) == tool_id_or_name.lower(),
                )
                res = await session.execute(stmt)
                model = res.scalar_one_or_none()
                if model:
                    return model.to_domain()

            # 3. Look up by name across all servers
            stmt = select(ToolModel).where(func.lower(ToolModel.name) == tool_id_or_name.lower())
            res = await session.execute(stmt)
            model = res.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list_tools(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ToolEntity], int]:
        async with self.session_factory() as session:
            stmt = select(ToolModel)

            if server_id is not None:
                stmt = stmt.where(ToolModel.server_id == str(server_id))
            if tool_name:
                stmt = stmt.where(func.lower(ToolModel.name) == tool_name.lower())
            if status:
                stmt = stmt.where(func.lower(ToolModel.availability_status) == status.lower())
            if search:
                term = f"%{search.lower()}%"
                stmt = stmt.where(
                    func.lower(ToolModel.name).like(term)
                    | func.lower(ToolModel.description).like(term)
                    | func.lower(ToolModel.server_name).like(term)
                )

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await session.execute(count_stmt)).scalar_one()

            # Sort by server_name, then name
            stmt = stmt.order_by(ToolModel.server_name.asc(), ToolModel.name.asc())

            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)

            result = await session.execute(stmt)
            models = result.scalars().all()
            return [m.to_domain() for m in models], total

    async def load_all_tools(self) -> list[ToolEntity]:
        async with self.session_factory() as session:
            stmt = select(ToolModel)
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [m.to_domain() for m in models]


class InMemoryToolRepository(ToolRepositoryAbstract):
    """In-memory implementation of ToolRepositoryAbstract."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntity] = {}
        self._lock = asyncio.Lock()

    async def save_server_tools(
        self,
        server_id: UUID,
        server_name: str,
        tools: list[ToolEntity],
    ) -> list[ToolEntity]:
        async with self._lock:
            # Clear existing tools for this server
            to_del = [k for k, v in self._tools.items() if v.server_id == server_id]
            for k in to_del:
                del self._tools[k]

            for tool in tools:
                self._tools[tool.id] = tool
            return tools

    async def delete_server_tools(self, server_id: UUID) -> None:
        async with self._lock:
            to_del = [k for k, v in self._tools.items() if v.server_id == server_id]
            for k in to_del:
                del self._tools[k]

    async def get_tool(
        self,
        tool_id_or_name: str,
        server_id: UUID | None = None,
    ) -> ToolEntity | None:
        async with self._lock:
            if tool_id_or_name in self._tools:
                return self._tools[tool_id_or_name]
            if server_id is not None:
                qualified = f"{server_id}:{tool_id_or_name}"
                if qualified in self._tools:
                    return self._tools[qualified]
            for tool in self._tools.values():
                if tool.name.lower() == tool_id_or_name.lower() and (
                    server_id is None or tool.server_id == server_id
                ):
                    return tool
            return None

    async def list_tools(
        self,
        server_id: UUID | None = None,
        tool_name: str | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ToolEntity], int]:
        async with self._lock:
            items = list(self._tools.values())

        if server_id is not None:
            items = [t for t in items if t.server_id == server_id]
        if tool_name:
            items = [t for t in items if t.name.lower() == tool_name.lower()]
        if status:
            items = [t for t in items if t.availability_status.lower() == status.lower()]
        if search:
            q = search.lower()
            items = [
                t
                for t in items
                if q in t.name.lower()
                or (t.description and q in t.description.lower())
                or q in t.server_name.lower()
            ]

        items.sort(key=lambda t: (t.server_name.lower(), t.name.lower()))
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end], total

    async def load_all_tools(self) -> list[ToolEntity]:
        async with self._lock:
            return list(self._tools.values())
