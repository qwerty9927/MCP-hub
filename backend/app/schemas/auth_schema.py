"""Authentication request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants.session_constants import DEFAULT_SESSION_IDLE_SECONDS, MAX_SESSION_IDLE_MINUTES, MIN_SESSION_IDLE_MINUTES

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., max_length=255, pattern=_EMAIL_PATTERN, description="Account email address")
    password: str = Field(..., min_length=8, max_length=128, description="Account password (8-128 characters)")

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime


_SESSION_IDLE_DESCRIPTION = (
    "Minutes without a tool call after which a Session opened with this key is marked completed "
    f"({MIN_SESSION_IDLE_MINUTES}-{MAX_SESSION_IDLE_MINUTES}). Null uses the default of "
    f"{DEFAULT_SESSION_IDLE_SECONDS // 60}. This is not the key's expiry."
)


class ApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100, description="Label to recognise the key by, e.g. 'laptop Claude'")
    session_idle_minutes: int | None = Field(
        default=None, ge=MIN_SESSION_IDLE_MINUTES, le=MAX_SESSION_IDLE_MINUTES, description=_SESSION_IDLE_DESCRIPTION
    )


class ApiKeyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_idle_minutes: int | None = Field(
        ...,
        ge=MIN_SESSION_IDLE_MINUTES,
        le=MAX_SESSION_IDLE_MINUTES,
        description=f"{_SESSION_IDLE_DESCRIPTION} Applies to Sessions opened afterwards.",
    )


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str = Field(..., description="First characters of the key, for recognition only")
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    session_idle_minutes: int | None = Field(default=None, description=_SESSION_IDLE_DESCRIPTION)


class ApiKeyCreatedResponse(ApiKeyResponse):
    key: str = Field(..., description="The full key. Shown only once; the hub stores only a hash")
