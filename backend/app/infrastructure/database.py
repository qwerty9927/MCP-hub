"""Database configuration and session management for PostgreSQL."""

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
from app.models.base_model import Base
from app.models.execution_model import ExecutionModel  # noqa: F401 - metadata discovery
from app.models.server_model import ServerModel  # noqa: F401 - metadata discovery
from app.models.session_model import SessionModel  # noqa: F401 - metadata discovery
from app.models.tool_model import ToolModel  # noqa: F401 - metadata discovery
from app.models.user_model import UserModel  # noqa: F401 - metadata discovery

_settings = get_settings()


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


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Initialize database tables."""
    database_engine = target_engine or engine
    async with database_engine.begin() as connection:
        # discovered_tools.embedding needs pgvector; create_all does not create extensions.
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)


engine = create_database_engine(_settings.DATABASE_URL, _settings.DEBUG)
async_session_factory = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)
