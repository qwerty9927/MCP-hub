"""Deprecated: MCPGatewayService has been renamed to MCPServer and moved to app.mcp.mcp_server."""

import warnings

from app.mcp.mcp_proxy_asgi import MCPProxyASGI as MCPGatewayProxyASGI
from app.mcp.mcp_server import MCPServer as MCPGatewayService

warnings.warn(
    "app.services.mcp_gateway is deprecated, use app.mcp.mcp_server instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MCPGatewayProxyASGI", "MCPGatewayService"]
