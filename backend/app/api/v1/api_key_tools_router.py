"""Console routes for per-API-key tool visibility (ADR-0007)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_principal, get_tool_access_service
from app.domain.principal_entity import Principal
from app.schemas.tool_access_schema import ApiKeyToolResponse, ApiKeyToolUpdateRequest, ApiKeyToolUpdateResponse
from app.services.tool_access_service import ToolAccessService

router = APIRouter(prefix="/auth/api-keys", tags=["Auth"])


@router.get(
    "/{api_key_id}/servers/{server_id}/tools",
    response_model=list[ApiKeyToolResponse],
    summary="List a server's tools with whether an API key can use each",
)
async def list_api_key_server_tools(
    api_key_id: UUID,
    server_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    tool_access: Annotated[ToolAccessService, Depends(get_tool_access_service)],
) -> list[ApiKeyToolResponse]:
    """Every key sees every tool until one is hidden from it."""
    return await tool_access.list_server_tools(api_key_id, server_id, user_id=principal.user_id)


@router.patch(
    "/{api_key_id}/servers/{server_id}/tools/{tool_name}",
    response_model=ApiKeyToolUpdateResponse,
    summary="Show or hide one of a server's tools for an API key",
)
async def set_api_key_tool_enabled(
    api_key_id: UUID,
    server_id: UUID,
    tool_name: str,
    payload: ApiKeyToolUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    tool_access: Annotated[ToolAccessService, Depends(get_tool_access_service)],
) -> ApiKeyToolUpdateResponse:
    """A hidden tool is left out of the key's SEARCH_TOOLS results, and running it with the key is rejected."""
    return await tool_access.set_tool_enabled(api_key_id, server_id, tool_name, payload.enabled, user_id=principal.user_id)
