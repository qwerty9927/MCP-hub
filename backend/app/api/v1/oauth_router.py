"""Connect hosted MCP servers with OAuth (ADR-0008)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_current_principal, get_oauth_service
from app.domain.principal_entity import Principal
from app.schemas.oauth_schema import OAuthConnectRequest, OAuthConnectResponse, OAuthProviderResponse
from app.services.oauth_service import OAuthService

router = APIRouter(tags=["OAuth"])


@router.get("/oauth/providers", response_model=list[OAuthProviderResponse], summary="List hosted MCP servers that connect with OAuth")
async def list_providers(
    principal: Annotated[Principal, Depends(get_current_principal)],
    oauth_service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> list[OAuthProviderResponse]:
    """The provider catalog, with whether each can be connected and how many the caller already has."""
    return await oauth_service.list_providers(user_id=principal.user_id)


@router.post("/oauth/connect", response_model=OAuthConnectResponse, summary="Start connecting a provider")
async def connect_provider(
    payload: OAuthConnectRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    oauth_service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> OAuthConnectResponse:
    """Return the URL where the user signs in. The server is created once the callback completes."""
    return await oauth_service.start(user_id=principal.user_id, provider_id=payload.provider_id, name=payload.name)


@router.post("/servers/{server_id}/oauth/reconnect", response_model=OAuthConnectResponse, summary="Sign in again to an OAuth server")
async def reconnect_server(
    server_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    oauth_service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> OAuthConnectResponse:
    """Return a fresh sign-in URL for a server whose tokens can no longer be refreshed."""
    return await oauth_service.reconnect(user_id=principal.user_id, server_id=server_id)


@router.get("/oauth/callback", summary="OAuth redirect target", include_in_schema=False)
async def oauth_callback(
    oauth_service: Annotated[OAuthService, Depends(get_oauth_service)],
    state: Annotated[str, Query(max_length=512)] = "",
    code: Annotated[str | None, Query(max_length=4096)] = None,
    iss: Annotated[str | None, Query(max_length=2048)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
    error_description: Annotated[str | None, Query(max_length=1024)] = None,
) -> RedirectResponse:
    """Public: the authorization server sends the browser here. The single-use state ties it to the sign-in
    (and so to the account) that started it. Ends by handing the result to the console's /oauth/complete."""
    reason = (error_description or error) if error else None
    result = await oauth_service.complete(state=state, code=code, iss=iss, error=reason)
    return RedirectResponse(oauth_service.complete_redirect_url(result), status_code=303)
