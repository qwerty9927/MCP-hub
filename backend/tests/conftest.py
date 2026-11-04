"""Pytest fixtures and configuration."""

import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import app.infrastructure.database as db_module  # noqa: E402
from app.api.dependencies import (  # noqa: E402
    _connection_manager,
    _execution_repo,
    _server_repo,
    _tool_catalog,
    _tool_repo,
    get_mcp_gateway,
)
from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.execution_model import ExecutionModel  # noqa: E402
from app.models.server_model import ServerModel  # noqa: E402
from app.models.tool_model import ToolModel  # noqa: E402

# Configure test engine with NullPool to prevent event loop cross-task issues in pytest-asyncio
_settings = get_settings()
db_module.engine = db_module.create_database_engine(_settings.DATABASE_URL, poolclass=NullPool)
db_module.async_session_factory = async_sessionmaker(
    bind=db_module.engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest.fixture(autouse=True)
async def cleanup_dependencies():
    """Ensure clean state before and after each test."""
    await db_module.init_db()
    yield
    # Cleanup state
    await _connection_manager.shutdown()

    if hasattr(_server_repo, "_servers"):
        _server_repo._servers.clear()
    else:
        async with db_module.async_session_factory() as session:
            await session.execute(delete(ToolModel))
            await session.execute(delete(ExecutionModel))
            await session.execute(delete(ServerModel))
            await session.commit()

    if hasattr(_execution_repo, "_executions"):
        _execution_repo._executions.clear()

    if hasattr(_tool_repo, "_tools"):
        _tool_repo._tools.clear()

    _tool_catalog._tools.clear()

    gateway = get_mcp_gateway()
    gateway._tool_map.clear()
    gateway._active_sessions.clear()

    await db_module.engine.dispose()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
