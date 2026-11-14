"""ASGI proxy application for MCPServer: authenticates every /mcp request, then hands it to the SDK."""

from typing import TYPE_CHECKING

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from starlette.authentication import AuthCredentials
from starlette.types import Receive, Scope, Send

from app.core.exceptions import UnauthorizedError
from app.domain.principal_entity import Principal
from app.helpers.tokens import is_api_key

if TYPE_CHECKING:
    from app.mcp.mcp_server import MCPServer


CONSOLE_CLIENT_ID = "console"


class MCPProxyASGI:
    """Pure ASGI application that authenticates the caller and dispatches to MCPServer's active session manager."""

    def __init__(self, mcp_server: "MCPServer") -> None:
        self.mcp_server = mcp_server

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            principal = await self._authenticate(scope)

            if principal is None:
                raise UnauthorizedError("A valid API key or console token is required")

            # if scope["method"] == "DELETE":
            #     await self._complete_session(scope, principal)

        await self.mcp_server.session_manager.asgi_app(scope, receive, send)

    async def _authenticate(self, scope: Scope) -> Principal | None:
        auth = self.mcp_server.auth_service
        token = _header(scope, b"x-api-key")
        if token and is_api_key(token):
            principal = await auth.authenticate_api_key(token)

            if principal is not None:
                scope["user"] = authenticated_user(principal, token)
                scope["auth"] = AuthCredentials([])

            return principal

        return None

    # async def _complete_session(self, scope: Scope, principal: Principal) -> None:
    #     session_id = _header(scope, b"mcp-session-id")
    #     session_repo = self.mcp_server.session_repo

    #     if not session_id or session_repo is None:
    #         return

    #     try:
    #         await session_repo.update_status(session_id, "completed", owner_id=principal.user_id)
    #     except Exception:
    #         logger.exception("Could not update session status on DELETE")


def authenticated_user(principal: Principal, token: str) -> AuthenticatedUser:
    """Create the SDK's authenticated user from a Principal.

    The SDK binds a handshake-era transport session to the credential that opened it (client_id + subject).
    Each API key or console login can only use the sessions it created. The Principal is stored in claims.
    """
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


# def _bearer_token(scope: Scope) -> str | None:
#     value = _header(scope, b"authorization")

#     if not value:
#         return None

#     if not value.lower().startswith("bearer "):
#         return value

#     return value[7:].strip()


# async def _send_unauthorized(send: Send, message: str) -> None:
#     correlation_id = get_correlation_id()
#     body = json.dumps(
#         {
#             "error": {
#                 "code": "401",
#                 "message": message,
#                 "details": {},
#                 "correlation_id": correlation_id,
#             }
#         }
#     ).encode()

#     await send(
#         {
#             "type": "http.response.start",
#             "status": 401,
#             "headers": [
#                 (b"content-type", b"application/json"),
#                 (b"www-authenticate", b'Bearer realm="mcp-hub"'),
#                 (b"x-correlation-id", correlation_id.encode("latin-1")),
#             ],
#         }
#     )
#     await send({"type": "http.response.body", "body": body})
