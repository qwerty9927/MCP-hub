"""Pytest fixtures and configuration."""

import os
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
    _tool_catalog,
    get_mcp_gateway,
)
from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.execution_model import ExecutionModel  # noqa: E402
from app.models.server_model import ServerModel  # noqa: E402
from app.models.session_model import SessionModel  # noqa: E402
from app.models.tool_model import ToolModel  # noqa: E402

# Configure test engine with NullPool to prevent event loop cross-task issues in pytest-asyncio.
# Allows overriding DATABASE_URL with TEST_DATABASE_URL to protect local development data.
_settings = get_settings()
_test_db_url = os.environ.get("TEST_DATABASE_URL", _settings.DATABASE_URL)
db_module.engine = db_module.create_database_engine(_test_db_url, poolclass=NullPool)
db_module.async_session_factory = async_sessionmaker(
    bind=db_module.engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest.fixture(scope="session", autouse=True)
async def initialize_test_database():
    """Ensure database schema is created once per test session rather than per test."""
    await db_module.init_db()


@pytest.fixture(autouse=True)
async def cleanup_dependencies():
    """Ensure clean state before and after each test."""
    yield
    # Cleanup state
    await _connection_manager.shutdown()

    async with db_module.async_session_factory() as session:
        await session.execute(delete(ToolModel))
        await session.execute(delete(ExecutionModel))
        await session.execute(delete(SessionModel))
        await session.execute(delete(ServerModel))
        await session.commit()

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
