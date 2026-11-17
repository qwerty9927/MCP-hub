"""A real streamable-HTTP MCP server protected by OAuth, built from the SDK's own auth server, for tests.

It auto-approves every authorization request (no login page), so a test plays the browser by fetching the
authorization URL and reading the code and state from the redirect.
"""

import secrets
import threading
import time

import uvicorn
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import MCPServer
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


class InMemoryAuthProvider:
    """Authorization server state; tests reach in to expire or revoke tokens."""

    def __init__(self, access_token_lifetime: int = 3600) -> None:
        self.access_token_lifetime = access_token_lifetime
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.refresh_count = 0

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.clients[client_info.client_id] = client_info

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        code = secrets.token_urlsafe(16)
        self.codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or [],
            expires_at=time.time() + 300,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> AuthorizationCode | None:
        return self.codes.get(authorization_code)

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode) -> OAuthToken:
        self.codes.pop(authorization_code.code, None)
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource)

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        return self.refresh_tokens.get(refresh_token)

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        self.refresh_tokens.pop(refresh_token.token, None)
        self.refresh_count += 1
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.resource)

    async def load_access_token(self, token: str) -> AccessToken | None:
        access = self.access_tokens.get(token)
        if access and access.expires_at and access.expires_at < time.time():
            return None
        return access

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.access_tokens.pop(token.token, None)
        self.refresh_tokens.pop(token.token, None)

    def revoke_everything(self) -> None:
        self.access_tokens.clear()
        self.refresh_tokens.clear()

    def _issue(self, client_id: str, scopes: list[str], resource: str | None) -> OAuthToken:
        access, refresh = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        expires_at = int(time.time()) + self.access_token_lifetime
        self.access_tokens[access] = AccessToken(token=access, client_id=client_id, scopes=scopes, expires_at=expires_at, resource=resource)
        self.refresh_tokens[refresh] = RefreshToken(token=refresh, client_id=client_id, scopes=scopes, resource=resource)
        return OAuthToken(access_token=access, expires_in=self.access_token_lifetime, refresh_token=refresh, scope=" ".join(scopes) or None)


class FakeOAuthMcpServer:
    """Runs the protected server on 127.0.0.1:`port` in a background thread."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.mcp_url = f"{self.base_url}/mcp"
        self.provider = InMemoryAuthProvider()
        mcp = MCPServer(
            "fake-oauth-server",
            auth_server_provider=self.provider,
            auth=AuthSettings(
                issuer_url=self.base_url,
                resource_server_url=self.mcp_url,
                client_registration_options=ClientRegistrationOptions(enabled=True),
                validate_token_resource=True,
            ),
        )

        @mcp.tool()
        def whoami() -> str:
            """Say who is calling."""
            return "an authenticated caller"

        self._server = uvicorn.Server(uvicorn.Config(mcp.streamable_http_app(), host="127.0.0.1", port=port, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> None:
        self._thread.start()
        deadline = time.time() + 5
        while not self._server.started and time.time() < deadline:
            time.sleep(0.05)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
