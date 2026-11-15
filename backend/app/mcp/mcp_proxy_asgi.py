"""ASGI proxy application for MCPServer: authenticates every /mcp request, then hands it to the SDK."""

from typing import TYPE_CHECKING

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from starlette.authentication import AuthCredentials
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core.exceptions import UnauthorizedError
from app.domain.principal_entity import Principal
from app.helpers.tokens import is_api_key

if TYPE_CHECKING:
    from app.mcp.mcp_server import MCPServer


CONSOLE_CLIENT_ID = "console"


class MCPProxyASGI:
    """Pure ASGI application that authenticates the caller and dispatches to MCPServer's session manager."""

    def __init__(self, mcp_server: "MCPServer") -> None:
        self.mcp_server = mcp_server

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            principal = await self._authenticate(scope)

            if principal is None:
                raise UnauthorizedError("A valid API key is required in the x-api-key header")

            if scope.get("method") != "POST":
                # Stateless (ADR-0004): no notification stream and no session to end. The SDK would hold a GET
                # open as an SSE stream forever, so refuse it here.
                response = JSONResponse(
                    {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Method Not Allowed: /mcp accepts POST only"}},
                    status_code=405,
                    headers={"Allow": "POST"},
                )
                await response(scope, receive, send)
                return

        await self.mcp_server.session_manager.asgi_app(scope, receive, send)

    async def _authenticate(self, scope: Scope) -> Principal | None:
        token = _header(scope, b"x-api-key")
        if not token or not is_api_key(token):
            return None

        principal = await self.mcp_server.auth_service.authenticate_api_key(token)
        if principal is not None:
            scope["user"] = authenticated_user(principal, token)
            scope["auth"] = AuthCredentials([])
        return principal


def authenticated_user(principal: Principal, token: str) -> AuthenticatedUser:
    """Wrap a Principal as the SDK's authenticated user; MCPServer reads the Principal back from its claims."""
    access = AccessToken(
        token=token,
        client_id=str(principal.api_key_id) if principal.api_key_id else CONSOLE_CLIENT_ID,
        subject=str(principal.user_id),
        scopes=[],
        claims={"principal": principal},
    )
    return AuthenticatedUser(access)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None
