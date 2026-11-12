"""ASGI proxy application for MCPServer: authenticates every /mcp request, then hands it to the SDK."""

import json
from typing import TYPE_CHECKING, Any

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from starlette.authentication import AuthCredentials

from app.core.logging import get_correlation_id, logger
from app.domain.principal_entity import Principal

if TYPE_CHECKING:
    from app.mcp.mcp_server import MCPServer

CONSOLE_CLIENT_ID = "console"


def _header(scope: Any, name: bytes) -> str | None:
    for key, val in scope.get("headers", []):
        if key.lower() == name:
            return val.decode("latin-1")
    return None


def _bearer_token(scope: Any) -> str | None:
    value = _header(scope, b"authorization")
    if not value or not value.lower().startswith("bearer "):
        return None
    token = value[7:].strip()
    return token or None


def authenticated_user(principal: Principal, token: str) -> AuthenticatedUser:
    """The SDK's user object for `principal`.

    The SDK binds a handshake-era transport session to the credential that opened it (client_id + subject), so
    each API key, or console login, can only use the sessions it created. The Principal rides along in `claims`.
    """
    access = AccessToken(
        token=token,
        client_id=str(principal.api_key_id) if principal.api_key_id else CONSOLE_CLIENT_ID,
        subject=str(principal.user_id),
        scopes=[],
        claims={"principal": principal},
    )
    return AuthenticatedUser(access)


async def _send_unauthorized(send: Any, message: str) -> None:
    corr_id = get_correlation_id()
    body = json.dumps({"error": {"code": "401", "message": message, "details": {}, "correlation_id": corr_id}}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b'Bearer realm="mcp-hub"'),
                (b"x-correlation-id", corr_id.encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class MCPProxyASGI:
    """Pure ASGI application that authenticates the caller and dispatches to MCPServer's active session manager."""

    def __init__(self, mcp_server: "MCPServer") -> None:
        self.mcp_server = mcp_server

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        session_manager = self.mcp_server.session_manager

        if scope.get("type") == "http":
            principal = await self._authenticate(scope)
            if principal is None:
                await _send_unauthorized(send, "A valid API key or console token is required")
                return

            # Intercept DELETE requests to mark the caller's own sessions completed
            if scope.get("method") == "DELETE":
                session_id = _header(scope, b"mcp-session-id")
                if session_id and self.mcp_server.session_repo:
                    try:
                        await self.mcp_server.session_repo.update_status(session_id, "completed", owner_id=principal.user_id)
                    except Exception as exc:
                        logger.warning(f"Could not update session status on DELETE: {exc}")

        await session_manager.asgi_app(scope, receive, send)

    async def _authenticate(self, scope: Any) -> Principal | None:
        auth = self.mcp_server.auth_service
        token = _bearer_token(scope)
        if auth is None or token is None:
            return None
        principal = await auth.authenticate(token)
        if principal is not None:
            scope["user"] = authenticated_user(principal, token)
            scope["auth"] = AuthCredentials([])
        return principal
