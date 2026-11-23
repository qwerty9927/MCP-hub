"""Account registration, console sign-in (login, refresh, logout), and API key management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.api.dependencies import get_auth_service, get_current_principal, require_console_client
from app.core.config import get_settings
from app.core.constants.auth_constants import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH_SUFFIX
from app.domain.principal_entity import Principal
from app.schemas.auth_schema import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService, ConsoleTokens

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
async def register(payload: RegisterRequest, auth_service: Annotated[AuthService, Depends(get_auth_service)]) -> UserResponse:
    """Self sign-up. Returns 403 when the hub has sign-up disabled."""
    return await auth_service.register(payload)


@router.post("/login", response_model=TokenResponse, summary="Log in and receive a console token")
async def login(
    payload: LoginRequest,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Exchange email and password for a short-lived JWT used by the admin console and REST API.

    Also sets the refresh token, an httpOnly cookie, which POST /auth/refresh exchanges for a new JWT (ADR-0009).
    """
    return _issue(response, await auth_service.login(payload))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange the refresh token cookie for a new console token",
    dependencies=[Depends(require_console_client)],
)
async def refresh(
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    """Rotates the refresh token: the cookie is replaced, and the old token stops working.

    Presenting a refresh token that was already used signs the whole sign-in out. Needs the `X-MCP-Hub-Client: console` header.
    """
    return _issue(response, await auth_service.refresh(refresh_token))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out: revoke the refresh token cookie",
    dependencies=[Depends(require_console_client)],
)
async def logout(
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> None:
    """Works without a valid console token, so an expired sign-in can still be ended. Access tokens already issued stay
    valid until they expire (ACCESS_TOKEN_EXPIRE_MINUTES)."""
    await auth_service.logout(refresh_token)
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=_cookie_path(),
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


@router.get("/me", response_model=UserResponse, summary="Get the signed-in account")
async def me(
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    return await auth_service.get_user(principal.user_id)


@router.get("/api-keys", response_model=list[ApiKeyResponse], summary="List the account's API keys")
async def list_api_keys(
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> list[ApiKeyResponse]:
    return await auth_service.list_api_keys(principal.user_id)


@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an API key for an MCP client",
)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiKeyCreatedResponse:
    """The full key is in this response only; the hub keeps a hash."""
    return await auth_service.create_api_key(principal.user_id, payload)


@router.patch("/api-keys/{key_id}", response_model=ApiKeyResponse, summary="Change an API key's Session idle timeout")
async def update_api_key(
    key_id: UUID,
    payload: ApiKeyUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiKeyResponse:
    """Set (or, with null, reset to the default) how long a Session opened with this key may sit idle. Not the key's expiry."""
    return await auth_service.update_api_key(principal.user_id, key_id, payload)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke an API key")
async def revoke_api_key(
    key_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth_service.revoke_api_key(principal.user_id, key_id)


def _issue(response: Response, tokens: ConsoleTokens) -> TokenResponse:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        tokens.refresh_token,
        max_age=tokens.refresh_max_age,
        path=_cookie_path(),
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
    response.headers["Cache-Control"] = "no-store"
    return tokens.access


def _cookie_path() -> str:
    return f"{get_settings().API_V1_STR}{REFRESH_COOKIE_PATH_SUFFIX}"
