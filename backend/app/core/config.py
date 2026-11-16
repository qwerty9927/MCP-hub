"""Application configuration module."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
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
    HOST: str
    PORT: int

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

    # Observability
    LOG_LEVEL: str

    # Tool search embeddings (fastembed, stored in pgvector). The column's size is fixed by a migration,
    # so EMBEDDING_DIMENSION must match it and the model.
    EMBEDDING_MODEL: str
    EMBEDDING_DIMENSION: int
    EMBEDDING_CACHE_DIR: str  # relative paths are resolved against the backend directory

    @field_validator("JWT_SECRET")
    @classmethod
    def _jwt_secret_is_long_enough(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def _expiry_is_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
