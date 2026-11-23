"""Application configuration module."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for the backend package
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """MCP Hub backend application settings.

    All configurations are required and loaded strictly from the .env file
    or environment variables without fallback in-code defaults.
    """

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", ".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    PROJECT_NAME: str
    VERSION: str
    ENVIRONMENT: Literal["development", "test", "production"]
    DEBUG: bool
    API_V1_STR: str

    # CORS
    CORS_ORIGINS: list[str]

    # Connection and Execution Timeouts
    DEFAULT_CONNECTION_TIMEOUT: float
    DEFAULT_EXECUTION_TIMEOUT: float
    MAX_CONCURRENT_EXECUTIONS_PER_SERVER: int

    # Security: Approved Executables for stdio transport
    ALLOWED_STDIO_EXECUTABLES: list[str]

    # Security: SSRF Protection
    ALLOW_PRIVATE_NETWORK_HTTP: bool

    # Database (PostgreSQL with asyncpg)
    DATABASE_URL: str

    # Authentication
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALLOW_SELF_SIGNUP: bool

    # Console refresh tokens (ADR-0009): an httpOnly cookie, rotated on every use
    REFRESH_TOKEN_EXPIRE_DAYS: int  # a refresh token unused this long expires; each rotation starts the clock again
    REFRESH_COOKIE_SECURE: bool  # true whenever the API is served over HTTPS
    REFRESH_COOKIE_SAMESITE: Literal["strict", "lax", "none"]  # "none" only when console and API are on different sites

    # Observability
    LOG_LEVEL: str

    # Tool search embeddings (fastembed, stored in pgvector). The column's size is fixed by a migration,
    # so EMBEDDING_DIMENSION must match it and the model.
    EMBEDDING_MODEL: str
    EMBEDDING_DIMENSION: int
    EMBEDDING_CACHE_DIR: str  # relative paths are resolved against the backend directory

    # OAuth connections to hosted MCP servers (ADR-0008)
    OAUTH_ENCRYPTION_KEY: str  # Fernet key encrypting stored OAuth tokens and client credentials
    PUBLIC_API_BASE_URL: str  # where browsers reach this API; the OAuth callback is built from it
    FRONTEND_BASE_URL: str  # where the console runs; the callback hands the result back to it
    OAUTH_CLIENTS: dict[str, dict[str, str]]  # provider id -> {client_id, client_secret} for providers without DCR
    OAUTH_FLOW_TIMEOUT_SECONDS: int  # how long a sign-in may stay open before it is abandoned

    @field_validator("OAUTH_ENCRYPTION_KEY")
    @classmethod
    def _oauth_key_is_fernet(cls, value: str) -> str:
        from cryptography.fernet import Fernet

        try:
            Fernet(value.encode())
        except ValueError as exc:
            raise ValueError("OAUTH_ENCRYPTION_KEY must be a Fernet key (Fernet.generate_key())") from exc
        return value

    @field_validator("PUBLIC_API_BASE_URL", "FRONTEND_BASE_URL")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("JWT_SECRET")
    @classmethod
    def _jwt_secret_is_long_enough(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES", "REFRESH_TOKEN_EXPIRE_DAYS")
    @classmethod
    def _expiry_is_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("token lifetimes must be positive")
        return value

    @model_validator(mode="after")
    def _samesite_none_needs_secure(self) -> "Settings":
        if self.REFRESH_COOKIE_SAMESITE == "none" and not self.REFRESH_COOKIE_SECURE:
            raise ValueError("REFRESH_COOKIE_SAMESITE=none requires REFRESH_COOKIE_SECURE=true")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
