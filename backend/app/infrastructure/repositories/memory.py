"""In-memory repository implementations."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.domain.entities import ExecutionEntity, ServerEntity, ToolEntity
from app.infrastructure.repositories.base import (
    ExecutionRepositoryBase,
    ServerRepositoryBase,
    ToolRepositoryBase,
)
from app.schemas.server import ServerHealthStatus, TransportType


class InMemoryServerRepository(ServerRepositoryBase):
    """In-memory implementation of ServerRepositoryBase."""

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


class InMemoryToolRepository(ToolRepositoryBase):
    """In-memory implementation of ToolRepositoryBase."""

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


class InMemoryExecutionRepository(ExecutionRepositoryBase):
    """In-memory implementation of ExecutionRepositoryBase."""

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
