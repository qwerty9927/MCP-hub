"""Account registration, login, and API key management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_auth_service, get_current_principal
from app.domain.principal_entity import Principal
from app.schemas.auth_schema import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
async def register(payload: RegisterRequest, auth: Annotated[AuthService, Depends(get_auth_service)]) -> UserResponse:
    """Self sign-up. Returns 403 when the hub has sign-up disabled."""
    return await auth.register(payload)


@router.post("/login", response_model=TokenResponse, summary="Log in and receive a console token")
async def login(payload: LoginRequest, auth: Annotated[AuthService, Depends(get_auth_service)]) -> TokenResponse:
    """Exchange email and password for a short-lived JWT used by the admin console and REST API."""
    return await auth.login(payload)


@router.get("/me", response_model=UserResponse, summary="Get the signed-in account")
async def me(
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    return await auth.get_user(principal.user_id)


@router.get("/api-keys", response_model=list[ApiKeyResponse], summary="List the account's API keys")
async def list_api_keys(
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> list[ApiKeyResponse]:
    return await auth.list_api_keys(principal.user_id)


@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an API key for an MCP client",
)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiKeyCreatedResponse:
    """The full key is in this response only; the hub keeps a hash."""
    return await auth.create_api_key(principal.user_id, payload)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke an API key")
async def revoke_api_key(
    key_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth.revoke_api_key(principal.user_id, key_id)
