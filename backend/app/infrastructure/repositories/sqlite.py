"""SQLite asynchronous repository implementations using SQLAlchemy 2.x."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain import ExecutionEntity, ServerEntity, ToolEntity
from app.infrastructure.database import async_session_factory
from app.infrastructure.repositories.base import (
    ExecutionRepositoryBase,
    ServerRepositoryBase,
    ToolRepositoryBase,
)
from app.models.execution import ExecutionModel
from app.models.server import ServerModel
from app.models.tool import ToolModel
from app.schemas.server import ServerHealthStatus, TransportType


class SqliteServerRepository(ServerRepositoryBase):
    """SQLite implementation of ServerRepositoryBase using SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker | None = None) -> None:
        self.session_factory = session_factory or async_session_factory

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


class SqliteToolRepository(ToolRepositoryBase):
    """SQLite implementation of ToolRepositoryBase using SQLAlchemy."""

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


class SqliteExecutionRepository(ExecutionRepositoryBase):
    """SQLite implementation of ExecutionRepositoryBase using SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker | None = None) -> None:
        self.session_factory = session_factory or async_session_factory

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
