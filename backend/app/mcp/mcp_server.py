import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from mcp import ListToolsResult
from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.session import ServerSession
from mcp.server.streamable_http_manager import (
    StreamableHTTPSessionManager,
    TransportSecuritySettings,
)
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from app.core.config import get_settings
from app.core.constants.meta_tools import (
    MULTI_EXECUTE_TOOLS_NAME,
    SEARCH_TOOLS_NAME,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger
from app.helpers.text import slugify
from app.mcp.mcp_proxy_asgi import MCPProxyASGI
from app.mcp.multi_execute_tools import (
    MULTI_EXECUTE_TOOLS_SCHEMA,
    get_multi_execute_tool_definition,
    handle_multi_execute_tools,
)
from app.mcp.search_tools import (
    SEARCH_TOOLS_SCHEMA,
    get_search_tool_definition,
    handle_search_tools,
)
from app.schemas.session import InitSessionRequest
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.session_explorer import SessionExplorerService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_router import ToolRouterService


class MCPServer(Server):
    """Exposes the MCP Hub as a unified, aggregated MCP server via Streamable HTTP."""

    def __init__(
        self,
        server_registry: ServerRegistryService,
        tool_catalog: ToolCatalogService,
        connection_manager: ConnectionManager,
        tool_router: ToolRouterService,
        session_explorer: SessionExplorerService,
    ) -> None:
        self.server_registry = server_registry
        self.tool_catalog = tool_catalog
        self.connection_manager = connection_manager
        self.tool_router = tool_router
        self.session_explorer = session_explorer

        self._active_sessions: set[ServerSession] = set()
        self._lock = asyncio.Lock()
        self._proxy_asgi = MCPProxyASGI(self)

        self._init_server()

    def _init_server(self) -> None:
        """Initialize or reset the lowlevel MCP Server and Streamable HTTP manager."""
        settings = get_settings()

        # In non-production environments, allow test and localhost host variations
        transport_security = None
        if settings.ENVIRONMENT != "production":
            transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
                allowed_hosts=["*"],
                allowed_origins=["*"],
            )

        super().__init__(
            name="mcp-hub-gateway",
            version=settings.VERSION,
            instructions="Unified MCP Gateway providing aggregated tools across downstream MCP servers.",
            on_list_tools=self.handle_list_tools,
            on_call_tool=self.handle_call_tool,
            get_tool_input_schema=self.get_tool_input_schema,
        )

        # Initialize streamable HTTP app and session manager on the server
        self.streamable_http_app(
            streamable_http_path="/mcp",
            transport_security=transport_security,
        )

        logger.info("Initialized MCPServer and Streamable HTTP manager on '/mcp'")

    @property
    def session_manager(self) -> StreamableHTTPSessionManager:
        """Return the current StreamableHTTPSessionManager."""
        assert self._session_manager is not None
        return self._session_manager

    def get_proxy_asgi_app(self) -> MCPProxyASGI:
        """Return the proxy ASGI application for mounting or adding to FastAPI routes."""
        return self._proxy_asgi

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        """Lifespan context manager that starts and stops the gateway session manager safely."""
        if self.session_manager._has_started:
            logger.info("Resetting StreamableHTTPSessionManager for fresh lifecycle run...")
            self._init_server()

        async with self.session_manager.run():
            logger.info("MCPServer Streamable HTTP Session Manager is active and serving.")
            yield
        logger.info("MCPServer Streamable HTTP Session Manager shut down.")

    async def handle_list_tools(
        self,
        ctx: ServerRequestContext,
        params: PaginatedRequestParams | None = None,
    ) -> ListToolsResult:
        """Handle incoming tools/list request from an upstream MCP client."""
        # Track active client session for list_changed notifications
        await self._init_session(ctx)

        mcp_tools: list[Tool] = [
            get_search_tool_definition(),
            get_multi_execute_tool_definition(),
        ]

        # Sort tools deterministically by name
        mcp_tools.sort(key=lambda t: t.name)
        return ListToolsResult(tools=mcp_tools)

    async def handle_call_tool(
        self,
        ctx: ServerRequestContext,
        params: CallToolRequestParams,
    ) -> CallToolResult:
        """Handle incoming tools/call request by routing strictly to meta-tools."""
        if (
            ctx.session is None
            or ctx.session._connection is None
            or ctx.session._connection.session_id is None
        ):
            return CallToolResult(
                is_error=True,
                content=[
                    TextContent(
                        type="text",
                        text="Header mcp-session-id is required",
                    )
                ],
            )

        session_id = ctx.session._connection.session_id
        await self._init_session(ctx)

        if params.name == SEARCH_TOOLS_NAME:
            return await self._handle_search_tools_call(params.arguments)

        if params.name == MULTI_EXECUTE_TOOLS_NAME:
            return await self._handle_multi_execute_tools_call(
                params.arguments, session_id=session_id
            )

        return CallToolResult(
            is_error=True,
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"Unknown tool: '{params.name}'. MCP Hub only exposes '{SEARCH_TOOLS_NAME}' "
                        f"and '{MULTI_EXECUTE_TOOLS_NAME}'. Please use '{SEARCH_TOOLS_NAME}' to find candidate tools "
                        f"and '{MULTI_EXECUTE_TOOLS_NAME}' to execute them."
                    ),
                )
            ],
        )

    def get_tool_input_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Return the JSON input schema for a given namespaced tool or meta-tool."""
        if tool_name == SEARCH_TOOLS_NAME:
            return SEARCH_TOOLS_SCHEMA
        if tool_name == MULTI_EXECUTE_TOOLS_NAME:
            return MULTI_EXECUTE_TOOLS_SCHEMA
        return None

    async def _init_session(self, ctx: ServerRequestContext) -> None:
        """Register or update an active session discovered from MCP client stream."""
        if ctx.session is None or ctx.session._connection is None:
            return

        self._active_sessions.add(ctx.session)
        connection = ctx.session._connection

        if connection.session_id is not None:
            info = connection.client_params.client_info if connection.client_params else None
            try:
                result = await self.session_explorer.init_session(
                    InitSessionRequest(
                        session_id=connection.session_id,
                        title=info.name if info else None,
                        metadata={
                            "client_name": info.name if info else None,
                            "client_version": info.version if info else None,
                            "protocol_version": connection.protocol_version,
                        },
                    )
                )
                if result is None:
                    logger.debug(f"Session '{connection.session_id}' already active or recorded")
            except Exception as exc:
                logger.warning(f"Could not register session '{connection.session_id}': {exc}")

    async def _handle_search_tools_call(
        self,
        arguments: dict[str, Any] | None,
    ) -> CallToolResult:
        """Handle execution of SEARCH_TOOLS querying directly from mcp_servers and discovered_tools."""
        try:
            # 1. Fetch enabled servers from mcp_servers table
            servers_response = await self.server_registry.list_servers(
                page=1, page_size=1000, enabled=True
            )
            enabled_servers = [s for s in servers_response.items if s.enabled]

            # 2. Collect candidate tools from discovered_tools for enabled servers
            candidates: list[dict[str, Any]] = []
            for srv in enabled_servers:
                tools_response = await self.tool_catalog.list_tools(
                    server_id=srv.id, page=1, page_size=1000
                )
                srv_slug = slugify(srv.name)

                for tool in tools_response.items:
                    if tool.availability_status == "AVAILABLE":
                        candidates.append(
                            {
                                "tool_slug": f"{srv_slug}__{tool.name}",
                                "server_id": str(srv.id),
                                "server_name": srv.name,
                                "original_name": tool.name,
                                "description": tool.description,
                                "input_schema": tool.input_schema,
                            }
                        )

            result_dict = handle_search_tools(
                arguments=arguments or {},
                candidates=candidates,
            )
            return CallToolResult(
                is_error=False,
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(result_dict, indent=2),
                    )
                ],
            )
        except ValidationError as err:
            logger.warning(f"Validation failure in {SEARCH_TOOLS_NAME}: {err.message}")
            return CallToolResult(
                is_error=True,
                content=[
                    TextContent(
                        type="text",
                        text=f"Argument validation failed: {err.message}",
                    )
                ],
            )
        except Exception as exc:
            logger.error(f"Error executing {SEARCH_TOOLS_NAME}: {exc}")
            return CallToolResult(
                is_error=True,
                content=[
                    TextContent(
                        type="text",
                        text=f"Error executing {SEARCH_TOOLS_NAME}: {exc}",
                    )
                ],
            )

    async def _handle_multi_execute_tools_call(
        self,
        arguments: dict[str, Any] | None,
        session_id: str | None = None,
    ) -> CallToolResult:
        """Handle execution of MULTI_EXECUTE_TOOLS resolving tools directly from mcp_servers and discovered_tools."""
        try:
            # Dynamic resolver querying mcp_servers and discovered_tools via services
            async def resolve_tool_by_slug(tool_slug: str) -> tuple[Any, Any] | None:
                if not tool_slug:
                    return None

                # Format 1: {server_slug}__{tool_name}
                if "__" in tool_slug:
                    srv_slug_part, tool_name_part = tool_slug.split("__", 1)
                    servers_resp = await self.server_registry.list_servers(
                        page=1, page_size=1000, enabled=True
                    )
                    for srv in servers_resp.items:
                        base_slug = slugify(srv.name)
                        short_id = str(srv.id).replace("-", "")[:6]
                        if srv_slug_part.lower() in (
                            base_slug.lower(),
                            f"{base_slug}_{short_id}".lower(),
                        ):
                            server_ent = await self.server_registry.get_server_entity(srv.id)
                            if not server_ent.enabled:
                                return None
                            try:
                                tool_ent = await self.tool_catalog.get_tool(
                                    tool_name_part, server_id=srv.id
                                )
                                return tool_ent, server_ent
                            except NotFoundError:
                                return None

                # Format 2: {server_id}:{tool_name}
                if ":" in tool_slug:
                    srv_id_part, tool_name_part = tool_slug.split(":", 1)
                    try:
                        srv_uuid = UUID(srv_id_part)
                        server_ent = await self.server_registry.get_server_entity(srv_uuid)
                        if not server_ent.enabled:
                            return None
                        tool_ent = await self.tool_catalog.get_tool(
                            tool_name_part, server_id=srv_uuid
                        )
                        return tool_ent, server_ent
                    except (ValueError, NotFoundError):
                        return None

                # Format 3: simple tool_name across enabled servers
                try:
                    tool_ent = await self.tool_catalog.get_tool(tool_slug)
                    server_ent = await self.server_registry.get_server_entity(tool_ent.server_id)
                    if server_ent.enabled:
                        return tool_ent, server_ent
                except NotFoundError:
                    pass

                return None

            result_dict = await handle_multi_execute_tools(
                arguments=arguments or {},
                tool_resolver=resolve_tool_by_slug,
                tool_router=self.tool_router,
                server_registry=self.server_registry,
                session_id=session_id,
            )
            return CallToolResult(
                is_error=False,
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(result_dict, indent=2),
                    )
                ],
            )
        except ValidationError as err:
            logger.warning(f"Validation failure in {MULTI_EXECUTE_TOOLS_NAME}: {err.message}")
            return CallToolResult(
                is_error=True,
                content=[
                    TextContent(
                        type="text",
                        text=f"Argument validation failed: {err.message}",
                    )
                ],
            )
        except Exception as exc:
            logger.error(f"Error executing {MULTI_EXECUTE_TOOLS_NAME}: {exc}")
            return CallToolResult(
                is_error=True,
                content=[
                    TextContent(
                        type="text",
                        text=f"Error executing {MULTI_EXECUTE_TOOLS_NAME}: {exc}",
                    )
                ],
            )

    async def notify_tools_changed(self) -> None:
        """Broadcast tools/list_changed notification to all currently connected upstream MCP client sessions."""
        dead_sessions: list[ServerSession] = []
        for session in list(self._active_sessions):
            try:
                await session.send_tool_list_changed()
            except Exception as exc:
                logger.debug(f"Failed to notify client session (likely disconnected): {exc}")
                dead_sessions.append(session)

        for session in dead_sessions:
            self._active_sessions.discard(session)
