"""Database configuration and session management for PostgreSQL."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.models.base_model import Base
from app.models.execution_model import ExecutionModel  # noqa: F401 - metadata discovery
from app.models.server_model import ServerModel  # noqa: F401 - metadata discovery
from app.models.tool_model import ToolModel  # noqa: F401 - metadata discovery

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


engine = create_database_engine(_settings.DATABASE_URL, _settings.DEBUG)

async_session_factory = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an asynchronous database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Initialize database tables."""
    eng = target_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
