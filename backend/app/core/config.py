"""Application configuration module."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.embedding_schema import EmbeddingModelSpec

# Base directory for the backend package
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# The fields APScheduler's CronTrigger accepts (SESSION_SWEEP_CRON keys)
_CRON_FIELDS = frozenset({"year", "month", "day", "week", "day_of_week", "hour", "minute", "second"})


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

    # App
    API_V1_STR: str
    DEBUG: bool
    ENVIRONMENT: Literal["development", "test", "production"]
    LOG_LEVEL: str
    PROJECT_NAME: str
    VERSION: str

    # Public URLs & CORS
    CORS_ORIGINS: list[str]
    FRONTEND_BASE_URL: str  # where the console runs; the callback hands the result back to it
    PUBLIC_API_BASE_URL: str  # where browsers reach this API; the OAuth callback is built from it

    # Database: PostgreSQL with asyncpg and pgvector
    DATABASE_URL: str

    # Authentication & console sessions: console access and refresh tokens (ADR-0009)
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALLOW_SELF_SIGNUP: bool
    JWT_SECRET: str
    REFRESH_COOKIE_SAMESITE: Literal["strict", "lax", "none"]  # "none" only when console and API are on different sites
    REFRESH_COOKIE_SECURE: bool  # true whenever the API is served over HTTPS
    REFRESH_TOKEN_EXPIRE_DAYS: int  # a refresh token unused this long expires; each rotation starts the clock again

    # Downstream MCP servers: timeouts, concurrency, stdio allowlist, SSRF protection
    ALLOWED_STDIO_EXECUTABLES: list[str]
    ALLOW_PRIVATE_NETWORK_HTTP: bool
    DEFAULT_CONNECTION_TIMEOUT: float
    DEFAULT_EXECUTION_TIMEOUT: float
    MAX_CONCURRENT_EXECUTIONS_PER_SERVER: int

    # OAuth connections: hosted MCP servers (ADR-0008)
    OAUTH_CLIENTS: dict[str, dict[str, str]]  # provider id -> {client_id, client_secret} for providers without DCR
    OAUTH_ENCRYPTION_KEY: str  # Fernet key encrypting stored OAuth tokens and client credentials
    OAUTH_FLOW_TIMEOUT_SECONDS: int  # how long a sign-in may stay open before it is abandoned

    # Tool search embeddings: stored in pgvector (ADR-0006, ADR-0010). The column's size is fixed by a migration,
    # so EMBEDDING_DIMENSION must match it and the model.
    EMBEDDING_CACHE_DIR: str  # local provider only; relative paths are resolved against the backend directory
    EMBEDDING_DIMENSION: int
    EMBEDDING_MODEL: str  # a key of EMBEDDING_MODELS; the same model whichever provider runs it
    EMBEDDING_MODELS: dict[str, EmbeddingModelSpec]  # JSON catalog: name -> dimension, id and pooling per provider
    EMBEDDING_PROVIDER: Literal["local", "cloudflare"]  # where vectors are computed (ADR-0010)
    # pgvector >= 0.8 iterative index scans, so filters cannot cut results short (ADR-0006). relaxed_order is not
    # offered: its rows are only roughly ordered by distance, which the search query's ordering relies on.
    HNSW_ITERATIVE_SCAN: Literal["strict_order", "off"]

    # Cloudflare Workers AI: EMBEDDING_PROVIDER=cloudflare; account and token may be empty otherwise
    CLOUDFLARE_ACCOUNT_ID: str
    CLOUDFLARE_API_BASE_URL: str  # Cloudflare API v4 root, e.g. https://api.cloudflare.com/client/v4
    CLOUDFLARE_API_TOKEN: str
    CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS: float  # between polls of a queued batch (EMBEDDING_BACKFILL_QUEUED)
    CLOUDFLARE_BATCH_TIMEOUT_SECONDS: float  # a queued batch not done by then is abandoned; the next backfill resubmits
    CLOUDFLARE_REQUEST_TIMEOUT_SECONDS: float  # per Workers AI request

    # Background jobs: APScheduler jobs (ADR-0005); each is safe to run on several hub instances
    # - Embedding backfill: embed Tools stored without an embedding (ADR-0006)
    EMBEDDING_BACKFILL_BATCH: int  # Tools embedded per model call
    EMBEDDING_BACKFILL_INTERVAL_MINUTES: int
    EMBEDDING_BACKFILL_JOB_ID: str
    EMBEDDING_BACKFILL_MISFIRE_GRACE_SECONDS: int
    # Embed through the provider's batch queue (Cloudflare Batch API): slower, but waits out capacity shortages
    # instead of failing. A provider without a queue (local) embeds directly either way (ADR-0010).
    EMBEDDING_BACKFILL_QUEUED: bool
    # - Refresh token purge: delete expired console refresh tokens (ADR-0009)
    REFRESH_TOKEN_PURGE_INTERVAL_MINUTES: int
    REFRESH_TOKEN_PURGE_JOB_ID: str
    REFRESH_TOKEN_PURGE_MISFIRE_GRACE_SECONDS: int
    # - Session sweep: complete idle Sessions (ADR-0005)
    SESSION_SWEEP_CRON: dict[str, str]  # JSON of APScheduler CronTrigger fields, UTC
    SESSION_SWEEP_JOB_ID: str
    SESSION_SWEEP_MISFIRE_GRACE_SECONDS: int

    @field_validator("OAUTH_ENCRYPTION_KEY")
    @classmethod
    def _oauth_key_is_fernet(cls, value: str) -> str:
        from cryptography.fernet import Fernet

        try:
            Fernet(value.encode())
        except ValueError as exc:
            raise ValueError("OAUTH_ENCRYPTION_KEY must be a Fernet key (Fernet.generate_key())") from exc
        return value

    @field_validator("CLOUDFLARE_API_BASE_URL")
    @classmethod
    def _cloudflare_url_is_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("CLOUDFLARE_API_BASE_URL must be an https:// URL (the API token travels in its requests)")
        return value.rstrip("/")

    @field_validator("CLOUDFLARE_REQUEST_TIMEOUT_SECONDS", "CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS", "CLOUDFLARE_BATCH_TIMEOUT_SECONDS")
    @classmethod
    def _cloudflare_timeout_is_positive(cls, value: float, info: ValidationInfo) -> float:
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive")
        return value

    @model_validator(mode="after")
    def _batch_poll_fits_its_timeout(self) -> "Settings":
        if self.CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS >= self.CLOUDFLARE_BATCH_TIMEOUT_SECONDS:
            raise ValueError("CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS must be shorter than CLOUDFLARE_BATCH_TIMEOUT_SECONDS")
        return self

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

    @field_validator(
        "EMBEDDING_BACKFILL_BATCH",
        "EMBEDDING_BACKFILL_INTERVAL_MINUTES",
        "EMBEDDING_BACKFILL_MISFIRE_GRACE_SECONDS",
        "SESSION_SWEEP_MISFIRE_GRACE_SECONDS",
        "REFRESH_TOKEN_PURGE_INTERVAL_MINUTES",
        "REFRESH_TOKEN_PURGE_MISFIRE_GRACE_SECONDS",
    )
    @classmethod
    def _job_setting_is_positive(cls, value: int, info: ValidationInfo) -> int:
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive")
        return value

    @field_validator("SESSION_SWEEP_CRON")
    @classmethod
    def _cron_uses_trigger_fields(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = sorted(set(value) - _CRON_FIELDS)
        if not value or unknown:
            raise ValueError(
                f"SESSION_SWEEP_CRON needs CronTrigger fields only ({', '.join(sorted(_CRON_FIELDS))}); got {unknown or 'none'}"
            )
        return value

    @model_validator(mode="after")
    def _job_ids_are_distinct(self) -> "Settings":
        ids = [self.EMBEDDING_BACKFILL_JOB_ID, self.SESSION_SWEEP_JOB_ID, self.REFRESH_TOKEN_PURGE_JOB_ID]
        if any(not job_id.strip() for job_id in ids) or len(set(ids)) != len(ids):
            raise ValueError(
                "EMBEDDING_BACKFILL_JOB_ID, SESSION_SWEEP_JOB_ID and REFRESH_TOKEN_PURGE_JOB_ID must be distinct and non-empty"
            )
        return self

    @model_validator(mode="after")
    def _embedding_source_is_usable(self) -> "Settings":
        spec = self.EMBEDDING_MODELS.get(self.EMBEDDING_MODEL)
        if spec is None:
            raise ValueError(f"EMBEDDING_MODEL must be one of {sorted(self.EMBEDDING_MODELS)}, got '{self.EMBEDDING_MODEL}'")
        if spec.dimension != self.EMBEDDING_DIMENSION:
            raise ValueError(f"EMBEDDING_DIMENSION is {self.EMBEDDING_DIMENSION}, but {self.EMBEDDING_MODEL} returns {spec.dimension}")
        if self.EMBEDDING_PROVIDER == "cloudflare":
            missing = [name for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN") if not getattr(self, name).strip()]
            if missing:
                raise ValueError(f"EMBEDDING_PROVIDER=cloudflare requires {', '.join(missing)}")
        return self

    @property
    def embedding_model_spec(self) -> EmbeddingModelSpec:
        """The EMBEDDING_MODELS entry EMBEDDING_MODEL names (validation guarantees it exists)."""
        return self.EMBEDDING_MODELS[self.EMBEDDING_MODEL]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
