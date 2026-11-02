"""Repository interfaces defining data persistence contracts."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain import ExecutionEntity, ServerEntity, ToolEntity
from app.schemas.server import ServerHealthStatus, TransportType


class ServerRepositoryBase(ABC):
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


class ToolRepositoryBase(ABC):
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


class ExecutionRepositoryBase(ABC):
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
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExecutionEntity], int]:
        """List executions with pagination and filtering."""
        pass
