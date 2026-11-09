"""ASGI proxy application for MCPServer."""

from typing import TYPE_CHECKING, Any

from app.core.logging import logger

if TYPE_CHECKING:
    from app.mcp.mcp_server import MCPServer


class MCPProxyASGI:
    """Pure ASGI application that dispatches dynamically to MCPServer's active session manager."""

    def __init__(self, mcp_server: "MCPServer") -> None:
        self.mcp_server = mcp_server

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        session_manager = self.mcp_server.session_manager

        # Intercept DELETE requests to mark sessions completed
        if scope.get("type") == "http" and scope.get("method") == "DELETE":
            session_id = None
            for name, val in scope.get("headers", []):
                if name.lower() == b"mcp-session-id":
                    session_id = val.decode("utf-8", errors="ignore")
                    break
            if session_id and self.mcp_server.session_repo:
                try:
                    await self.mcp_server.session_repo.update_status(session_id, "completed")
                except Exception as exc:
                    logger.warning(f"Could not update session status on DELETE: {exc}")

        await session_manager.asgi_app(scope, receive, send)
