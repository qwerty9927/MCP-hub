"""Application configuration module."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

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

    # Observability
    LOG_LEVEL: str


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
