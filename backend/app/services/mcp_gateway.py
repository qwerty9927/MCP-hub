"""MCP Gateway Service for exposing the hub as an aggregated MCP Server via Streamable HTTP."""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.session import ServerSession
from mcp.server.streamable_http_manager import (
    StreamableHTTPSessionManager,
    TransportSecuritySettings,
)

from app.core.config import get_settings
from app.core.exceptions import AppValidationError, ServerDisabledError, ToolNotFoundError
from app.core.logging import logger
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_router import ToolRouterService


@dataclass
class GatewayToolMapping:
    """Explicit mapping from Hub namespaced tool identifier to downstream server and tool."""

    hub_tool_name: str
    server_id: UUID
    server_name: str
    original_tool_name: str
    input_schema: dict[str, Any]
    description: str | None
    availability_status: str


class HubGatewayServer(Server):
    """Subclass of MCP lowlevel Server that advertises tool change notifications capability."""

    def create_initialization_options(
        self,
        notification_options: NotificationOptions | None = None,
        experimental_capabilities: dict[str, dict[str, Any]] | None = None,
        extensions: dict[str, dict[str, Any]] | None = None,
    ) -> InitializationOptions:
        notif = notification_options or NotificationOptions(tools_changed=True)
        return super().create_initialization_options(
            notification_options=notif,
            experimental_capabilities=experimental_capabilities,
            extensions=extensions,
        )


class MCPGatewayProxyASGI:
    """Pure ASGI application that dispatches dynamically to the gateway's active session manager."""

    def __init__(self, gateway_service: "MCPGatewayService") -> None:
        self.gateway_service = gateway_service

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        session_manager = self.gateway_service.session_manager
        await session_manager.asgi_app(scope, receive, send)


class MCPGatewayService:
    """Exposes the MCP Hub as a unified, aggregated MCP server via Streamable HTTP."""

    def __init__(
        self,
        server_registry: ServerRegistryService,
        tool_catalog: ToolCatalogService,
        connection_manager: ConnectionManager,
        tool_router: ToolRouterService,
    ) -> None:
        self.server_registry = server_registry
        self.tool_catalog = tool_catalog
        self.connection_manager = connection_manager
        self.tool_router = tool_router

        self._tool_map: dict[str, GatewayToolMapping] = {}
        self._active_sessions: set[ServerSession] = set()
        self._lock = asyncio.Lock()
        self._server: HubGatewayServer | None = None
        self._proxy_asgi = MCPGatewayProxyASGI(self)

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

        self._server = HubGatewayServer(
            name="mcp-hub-gateway",
            version=settings.VERSION,
            instructions="Unified MCP Gateway providing aggregated tools across downstream MCP servers.",
            on_list_tools=self.handle_list_tools,
            on_call_tool=self.handle_call_tool,
            get_tool_input_schema=self.get_tool_input_schema,
        )

        # Initialize streamable HTTP app and session manager on the server
        self._server.streamable_http_app(
            streamable_http_path="/mcp",
            transport_security=transport_security,
        )
        logger.info("Initialized HubGatewayServer and Streamable HTTP manager on '/mcp'")

    @property
    def server(self) -> HubGatewayServer:
        """Return the current HubGatewayServer instance."""
        if self._server is None:
            self._init_server()
        assert self._server is not None
        return self._server

    @property
    def session_manager(self) -> StreamableHTTPSessionManager:
        """Return the current StreamableHTTPSessionManager."""
        return self.server._session_manager

    def get_proxy_asgi_app(self) -> MCPGatewayProxyASGI:
        """Return the proxy ASGI application for mounting or adding to FastAPI routes."""
        return self._proxy_asgi

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        """Lifespan context manager that starts and stops the gateway session manager safely."""
        # If the manager was already started in a previous run, reinitialize server for clean lifecycle
        if self.session_manager._has_started:
            logger.info("Resetting StreamableHTTPSessionManager for fresh lifecycle run...")
            self._init_server()

        async with self.session_manager.run():
            logger.info("MCP Gateway Streamable HTTP Session Manager is active and serving.")
            yield
        logger.info("MCP Gateway Streamable HTTP Session Manager shut down.")

    @staticmethod
    def _slugify_name(name: str) -> str:
        """Convert a server name to a safe alphanumeric snake_case slug."""
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip()).strip("_").lower()
        return cleaned if cleaned else "server"

    async def refresh_tool_mappings(self) -> dict[str, GatewayToolMapping]:
        """Aggregate tools from all enabled and available downstream servers into the tool mapping."""
        async with self._lock:
            # 1. Fetch all registered servers
            servers_response = await self.server_registry.list_servers(page=1, page_size=1000)
            enabled_servers = [s for s in servers_response.items if s.enabled]

            new_tool_map: dict[str, GatewayToolMapping] = {}

            for srv in enabled_servers:
                slug = self._slugify_name(srv.name)

                # Fetch cached or persisted tools for this server
                tools_response = await self.tool_catalog.list_tools(
                    server_id=srv.id, page=1, page_size=1000
                )
                tools = tools_response.items

                # If no tools in catalog yet and server is healthy, attempt an auto-refresh
                if not tools and srv.health_status == "HEALTHY":
                    try:
                        server_ent = await self.server_registry.get_server_entity(srv.id)
                        refreshed = await self.tool_catalog.refresh_server_tools(
                            server_ent, self.connection_manager
                        )
                        tools_response = await self.tool_catalog.list_tools(
                            server_id=srv.id, page=1, page_size=1000
                        )
                        tools = tools_response.items
                        await self.server_registry.update_health(
                            srv.id, srv.health_status, len(refreshed)
                        )
                    except Exception as exc:
                        logger.warning(
                            f"Could not auto-refresh tools for server '{srv.name}': {exc}"
                        )

                for tool in tools:
                    # Construct namespaced tool name: <server_slug>__<tool_name>
                    candidate_name = f"{slug}__{tool.name}"

                    # Handle duplicate server slugs across different servers
                    if (
                        candidate_name in new_tool_map
                        and new_tool_map[candidate_name].server_id != srv.id
                    ):
                        short_id = str(srv.id).replace("-", "")[:6]
                        candidate_name = f"{slug}_{short_id}__{tool.name}"

                    new_tool_map[candidate_name] = GatewayToolMapping(
                        hub_tool_name=candidate_name,
                        server_id=srv.id,
                        server_name=srv.name,
                        original_tool_name=tool.name,
                        input_schema=tool.input_schema,
                        description=tool.description,
                        availability_status=tool.availability_status,
                    )

            self._tool_map = new_tool_map
            logger.info(
                f"Aggregated {len(self._tool_map)} tools from {len(enabled_servers)} enabled downstream servers"
            )
            return self._tool_map

    async def handle_list_tools(
        self,
        ctx: Any,
        params: types.PaginatedRequestParams | None = None,
    ) -> types.ListToolsResult:
        """Handle incoming tools/list request from an upstream MCP client."""
        # Track active client session for list_changed notifications
        if hasattr(ctx, "session") and ctx.session is not None:
            self._active_sessions.add(ctx.session)

        # Refresh downstream tool mappings dynamically
        await self.refresh_tool_mappings()

        mcp_tools: list[types.Tool] = []
        for mapping in self._tool_map.values():
            mcp_tools.append(
                types.Tool(
                    name=mapping.hub_tool_name,
                    description=mapping.description
                    or f"Tool '{mapping.original_tool_name}' from {mapping.server_name}",
                    inputSchema=mapping.input_schema,
                )
            )

        # Sort tools deterministically by namespaced name
        mcp_tools.sort(key=lambda t: t.name)
        return types.ListToolsResult(tools=mcp_tools)

    def get_tool_input_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Return the JSON input schema for a given namespaced tool."""
        mapping = self._tool_map.get(tool_name)
        return mapping.input_schema if mapping else None

    async def handle_call_tool(
        self,
        ctx: Any,
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        """Handle incoming tools/call request by routing to the downstream MCP server."""
        # 1. Resolve namespaced tool identifier via explicit mapping
        mapping = self._tool_map.get(params.name)
        if not mapping:
            # Try refreshing once in case downstream servers were newly updated
            await self.refresh_tool_mappings()
            mapping = self._tool_map.get(params.name)

        if not mapping:
            logger.warning(f"Gateway received call for unknown or unmapped tool: '{params.name}'")
            return types.CallToolResult(
                is_error=True,
                content=[
                    types.TextContent(
                        type="text", text=f"Unknown or unavailable tool: '{params.name}'"
                    )
                ],
            )

        # 2. Check downstream server status
        try:
            server = await self.server_registry.get_server_entity(mapping.server_id)
            if not server.enabled:
                return types.CallToolResult(
                    is_error=True,
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Target server '{mapping.server_name}' is currently disabled",
                        )
                    ],
                )
        except Exception as exc:
            return types.CallToolResult(
                is_error=True,
                content=[types.TextContent(type="text", text=f"Server lookup failed: {exc}")],
            )

        # 3. Forward call through ToolRouterService to invoke the downstream MCP server
        try:
            logger.info(
                f"Gateway forwarding tool '{params.name}' -> downstream server '{mapping.server_name}' "
                f"({mapping.server_id}) tool '{mapping.original_tool_name}'"
            )
            result = await self.tool_router.execute_mcp_tool(
                server_id=mapping.server_id,
                tool_name=mapping.original_tool_name,
                arguments=params.arguments or {},
            )
            return result

        except AppValidationError as err:
            logger.warning(f"Validation failure executing '{params.name}': {err.message}")
            return types.CallToolResult(
                is_error=True,
                content=[
                    types.TextContent(
                        type="text", text=f"Argument validation failed: {err.message}"
                    )
                ],
            )
        except ServerDisabledError:
            return types.CallToolResult(
                is_error=True,
                content=[
                    types.TextContent(
                        type="text", text=f"Server '{mapping.server_name}' is disabled"
                    )
                ],
            )
        except ToolNotFoundError:
            return types.CallToolResult(
                is_error=True,
                content=[
                    types.TextContent(
                        type="text", text=f"Tool '{mapping.original_tool_name}' not found on server"
                    )
                ],
            )
        except Exception as exc:
            logger.error(f"Error executing tool '{params.name}' through gateway: {exc}")
            return types.CallToolResult(
                is_error=True,
                content=[types.TextContent(type="text", text=f"Downstream execution error: {exc}")],
            )

    async def notify_tools_changed(self) -> None:
        """Broadcast tools/list_changed notification to all currently connected upstream MCP client sessions."""
        await self.refresh_tool_mappings()

        dead_sessions: list[ServerSession] = []
        for session in list(self._active_sessions):
            try:
                await session.send_tool_list_changed()
            except Exception as exc:
                logger.debug(f"Failed to notify client session (likely disconnected): {exc}")
                dead_sessions.append(session)

        for session in dead_sessions:
            self._active_sessions.discard(session)
