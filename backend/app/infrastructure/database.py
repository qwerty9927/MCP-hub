"""Database configuration and session management for PostgreSQL.

`Database` owns the engine and the session factory repositories open sessions from. Both are created on first use,
so importing the app connects to nothing. The app shares one instance, `database`; repositories receive it through
their constructor (see app/api/dependencies.py), and tests point it at their own database with `configure()`.
"""

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.models.api_key_disabled_tool_model import ApiKeyDisabledToolModel  # noqa: F401 - metadata discovery
from app.models.api_key_model import ApiKeyModel  # noqa: F401 - metadata discovery
from app.models.auth_rate_limit_model import AuthRateLimitModel  # noqa: F401 - metadata discovery
from app.models.base_model import Base
from app.models.execution_model import ExecutionModel  # noqa: F401 - metadata discovery
from app.models.refresh_token_model import RefreshTokenModel  # noqa: F401 - metadata discovery
from app.models.server_model import ServerModel  # noqa: F401 - metadata discovery
from app.models.server_oauth_credential_model import ServerOAuthCredentialModel  # noqa: F401 - metadata discovery
from app.models.session_model import SessionModel  # noqa: F401 - metadata discovery
from app.models.tool_model import ToolModel  # noqa: F401 - metadata discovery
from app.models.user_model import UserModel  # noqa: F401 - metadata discovery


def create_database_engine(
    url: str,
    debug: bool = False,
    poolclass: type | None = None,
) -> AsyncEngine:
    """Create a configured async database engine for PostgreSQL."""
    if poolclass is not None:
        return create_async_engine(url, echo=debug, poolclass=poolclass)
    return create_async_engine(
        url,
        echo=debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )


class Database:
    """A PostgreSQL database: its engine, and the sessions opened on it. The engine is created on first use."""

    def __init__(
        self,
        url: str | Callable[[], str],
        *,
        debug: bool | Callable[[], bool] = False,
        poolclass: type | None = None,
    ) -> None:
        """`url` and `debug` may be callables, read when the engine is first needed (the app's read settings then)."""
        self._url = url
        self._debug = debug
        self._poolclass = poolclass
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @classmethod
    def from_settings(cls) -> "Database":
        """The app's database: DATABASE_URL and DEBUG, read on first use."""
        return cls(lambda: get_settings().DATABASE_URL, debug=lambda: get_settings().DEBUG)

    def configure(self, url: str, *, poolclass: type | None = None, debug: bool = False) -> None:
        """Point this database at `url` (tests use their own database). Only before the engine is first used."""
        if self._engine is not None:
            raise RuntimeError("Database.configure() must be called before the engine is first used")
        self._url = url
        self._poolclass = poolclass
        self._debug = debug

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            url = self._url() if callable(self._url) else self._url
            debug = self._debug() if callable(self._debug) else self._debug
            self._engine = create_database_engine(url, debug, poolclass=self._poolclass)
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                autoflush=False,
                expire_on_commit=False,
                class_=AsyncSession,
            )
        return self._engine

    def session(self) -> AsyncSession:
        """A new session; use it as `async with database.session() as session:` and commit what it writes."""
        if self._session_factory is None:
            self.engine  # noqa: B018 - creates the engine and the session factory
        assert self._session_factory is not None
        return self._session_factory()

    async def create_schema(self) -> None:
        """Create the pgvector extension and every table that does not exist yet (tests; production uses Alembic)."""
        async with self.engine.begin() as connection:
            # discovered_tools.embedding needs pgvector; create_all does not create extensions.
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """Close the engine's pooled connections. The engine stays usable and reconnects on demand."""
        if self._engine is not None:
            await self._engine.dispose()


# The app's database, shared by every repository the app builds.
database = Database.from_settings()
