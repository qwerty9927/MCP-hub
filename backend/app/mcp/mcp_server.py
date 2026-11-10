"""MCP Server implementation for exposing the hub via Streamable HTTP."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.session import ServerSession
from mcp.server.streamable_http_manager import (
    StreamableHTTPSessionManager,
    TransportSecuritySettings,
)
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from app.core.config import get_settings
from app.core.constants.meta_tools import (
    MULTI_EXECUTE_TOOLS_NAME,
    SEARCH_TOOLS_NAME,
)
from app.core.exceptions import ValidationError
from app.core.logging import logger
from app.infrastructure.repositories.session_repository import SessionRepositoryAbstract
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
from app.services.connection_manager import ConnectionManager
from app.services.server_registry import ServerRegistryService
from app.services.tool_catalog import ToolCatalogService
from app.services.tool_executor import ToolExecutor


class MCPServer:
    """Exposes the MCP Hub as a unified, aggregated MCP server via Streamable HTTP."""

    def __init__(
        self,
        server_registry: ServerRegistryService,
        tool_catalog: ToolCatalogService,
        connection_manager: ConnectionManager,
        tool_executor: ToolExecutor,
        session_repository: SessionRepositoryAbstract | None = None,
    ) -> None:
        self.server_registry = server_registry
        self.tool_catalog = tool_catalog
        self.connection_manager = connection_manager
        self.tool_executor = tool_executor
        self.session_repo = session_repository

        self._active_sessions: set[ServerSession] = set()
        self._server: _HubServer | None = None
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

        self._server = _HubServer(
            name="mcp-hub-server",
            version=settings.VERSION,
            instructions="Unified MCP Server providing Search and Multi-Execute across connected MCP servers.",
            on_list_tools=self.handle_list_tools,
            on_call_tool=self.handle_call_tool,
            get_tool_input_schema=self.get_tool_input_schema,
        )

        # Initialize streamable HTTP app and session manager on the server
        self._server.streamable_http_app(
            streamable_http_path="/mcp",
            transport_security=transport_security,
        )
        logger.info("Initialized HubServer and Streamable HTTP manager on '/mcp'")

    @property
    def server(self) -> "_HubServer":
        """Return the current HubServer instance."""
        if self._server is None:
            self._init_server()
        assert self._server is not None
        return self._server

    @property
    def session_manager(self) -> StreamableHTTPSessionManager:
        """Return the current StreamableHTTPSessionManager."""
        assert self.server._session_manager is not None
        return self.server._session_manager

    def get_proxy_asgi_app(self) -> MCPProxyASGI:
        """Return the proxy ASGI application for mounting or adding to FastAPI routes."""
        return self._proxy_asgi

    @asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        """Lifespan context manager that starts and stops the server session manager safely."""
        if self.session_manager._has_started:
            logger.info("Resetting StreamableHTTPSessionManager for fresh lifecycle run...")
            self._init_server()

        async with self.session_manager.run():
            logger.info("MCPServer Streamable HTTP Session Manager is active and serving.")
            yield
        logger.info("MCPServer Streamable HTTP Session Manager shut down.")

    def _discover_session_id(self, ctx: ServerRequestContext) -> str | None:
        """Discover session ID from ServerRequestContext HTTP request headers or session connection."""
        if ctx.request and hasattr(ctx.request, "headers"):
            header_id = ctx.request.headers.get("mcp-session-id")
            if header_id:
                return header_id
        conn = getattr(ctx.session, "_connection", None)
        if conn and isinstance(getattr(conn, "session_id", None), str):
            return conn.session_id
        return None

    async def handle_list_tools(
        self,
        ctx: ServerRequestContext,
        params: PaginatedRequestParams | None = None,
    ) -> ListToolsResult:
        """Handle incoming tools/list request from an upstream MCP client."""
        self._active_sessions.add(ctx.session)
        session_id = self._discover_session_id(ctx)
        if session_id:
            await self._ensure_session_registered(ctx, session_id)

        # Strictly two tools are supported
        mcp_tools: list[Tool] = [
            get_search_tool_definition(),
            get_multi_execute_tool_definition(),
        ]
        return ListToolsResult(tools=mcp_tools)

    def get_tool_input_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Return the JSON input schema for the supported tools."""
        if tool_name in (SEARCH_TOOLS_NAME, "Search", "search"):
            return SEARCH_TOOLS_SCHEMA
        if tool_name in (
            MULTI_EXECUTE_TOOLS_NAME,
            "Multi-Execute",
            "multi_execute",
            "multi-execute",
        ):
            return MULTI_EXECUTE_TOOLS_SCHEMA
        return None

    async def handle_call_tool(
        self,
        ctx: ServerRequestContext,
        params: CallToolRequestParams,
    ) -> CallToolResult:
        """Handle incoming tools/call request by routing to Search or Multi-Execute."""
        session_id = self._discover_session_id(ctx)
        if session_id:
            await self._ensure_session_registered(ctx, session_id)

        if params.name in (SEARCH_TOOLS_NAME, "Search", "search"):
            return await self._handle_search_tools_call(params.arguments)

        if params.name in (
            MULTI_EXECUTE_TOOLS_NAME,
            "Multi-Execute",
            "multi_execute",
            "multi-execute",
        ):
            return await self._handle_multi_execute_tools_call(params.arguments, session_id=session_id)

        return CallToolResult(
            is_error=True,
            content=[
                TextContent(
                    type="text",
                    text=(f"Unsupported tool: '{params.name}'. Only {SEARCH_TOOLS_NAME} and {MULTI_EXECUTE_TOOLS_NAME} are supported."),
                )
            ],
        )

    async def _handle_search_tools_call(
        self,
        arguments: dict[str, Any] | None,
    ) -> CallToolResult:
        """Handle execution of Search based on mcp_servers and discovered_tools."""
        try:
            # Fetch enabled servers from mcp_servers table
            servers_res = await self.server_registry.list_servers(page=1, page_size=1000, enabled=True)
            enabled_server_ids = {s.id for s in servers_res.items}

            # Fetch discovered tools from discovered_tools table
            all_tools_res = await self.tool_catalog.list_tools(page=1, page_size=1000)
            candidate_tools = [t for t in all_tools_res.items if t.server_id in enabled_server_ids and t.availability_status == "AVAILABLE"]

            result_dict = handle_search_tools(
                arguments=arguments or {},
                tools=candidate_tools,
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
        """Handle execution of Multi-Execute based on mcp_servers and discovered_tools."""
        try:
            result_dict = await handle_multi_execute_tools(
                arguments=arguments or {},
                executor=self.tool_executor,
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

    async def _ensure_session_registered(self, ctx: ServerRequestContext, session_id: str) -> None:
        """Register or update an active session discovered from ServerRequestContext."""
        if not self.session_repo:
            return
        title = None
        metadata = None
        try:
            client_params = ctx.session.client_params
            if client_params and client_params.client_info:
                info = client_params.client_info
                title = f"{info.name} ({session_id[:8]})"
                metadata = {
                    "client_name": info.name,
                    "client_version": info.version,
                    "protocol_version": ctx.protocol_version or getattr(ctx.session, "protocol_version", None),
                }
        except Exception:
            pass

        try:
            await self.session_repo.get_or_create(
                session_id=session_id,
                title=title,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(f"Could not register session '{session_id}': {exc}")

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


class _HubServer(Server):
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
