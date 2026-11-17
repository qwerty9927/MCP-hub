"""Per-API-key tool visibility, for the console (ADR-0007). Every key sees every tool until one is hidden from it."""

from uuid import UUID

from app.core.exceptions import NotFoundError
from app.core.logging import logger
from app.infrastructure.repositories.api_key_repository import ApiKeyRepositoryAbstract
from app.infrastructure.repositories.tool_access_repository import ToolAccessRepositoryAbstract
from app.infrastructure.repositories.tool_repository import ToolRepositoryAbstract
from app.schemas.tool_access_schema import ApiKeyToolResponse, ApiKeyToolUpdateResponse
from app.services.server_registry import ServerRegistryService

MAX_TOOLS_PER_SERVER = 1000


class ToolAccessService:
    """Lists and changes which of a server's tools one of the owner's API keys can use."""

    def __init__(
        self,
        api_key_repository: ApiKeyRepositoryAbstract,
        server_registry: ServerRegistryService,
        tool_repository: ToolRepositoryAbstract,
        tool_access_repository: ToolAccessRepositoryAbstract,
    ) -> None:
        self._api_key_repository = api_key_repository
        self._server_registry = server_registry
        self._tool_repository = tool_repository
        self._tool_access_repository = tool_access_repository

    async def list_server_tools(self, api_key_id: UUID, server_id: UUID, *, user_id: UUID) -> list[ApiKeyToolResponse]:
        """The server's tools, each with whether the key can use it. 404 for another account's key or server."""
        await self._check_owner(api_key_id, server_id, user_id)
        tools, _ = await self._tool_repository.list_tools(server_id=server_id, page=1, page_size=MAX_TOOLS_PER_SERVER, user_id=user_id)
        disabled = await self._tool_access_repository.disabled_tool_names(api_key_id, server_id)
        return [
            ApiKeyToolResponse(tool_id=tool.id, name=tool.name, description=tool.description, enabled=tool.name not in disabled)
            for tool in sorted(tools, key=lambda tool: tool.name)
        ]

    async def set_tool_enabled(
        self, api_key_id: UUID, server_id: UUID, tool_name: str, enabled: bool, *, user_id: UUID
    ) -> ApiKeyToolUpdateResponse:
        """Show or hide one of the server's tools for the key. 404 when the tool is not on the server."""
        await self._check_owner(api_key_id, server_id, user_id)
        tool = await self._tool_repository.get_tool(tool_name, server_id=server_id, user_id=user_id)
        if tool is None:
            raise NotFoundError(
                f"Tool '{tool_name}' not found on server '{server_id}'",
                details={"tool_name": tool_name, "server_id": str(server_id)},
            )
        await self._tool_access_repository.set_enabled(api_key_id, server_id, tool.name, enabled)
        logger.info(f"{'Showed' if enabled else 'Hid'} tool '{tool.name}' of server {server_id} for API key {api_key_id}")
        return ApiKeyToolUpdateResponse(tool_name=tool.name, enabled=enabled)

    async def _check_owner(self, api_key_id: UUID, server_id: UUID, user_id: UUID) -> None:
        if await self._api_key_repository.get_active(user_id, api_key_id) is None:
            raise NotFoundError(f"API key '{api_key_id}' not found", details={"api_key_id": str(api_key_id)})
        await self._server_registry.get_server_entity(server_id, user_id=user_id)
