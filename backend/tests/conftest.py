"""Pytest fixtures and configuration."""

import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.api.dependencies import (  # noqa: E402
    _connection_manager,
    _execution_repo,
    _server_repo,
    _tool_catalog,
    _tool_repo,
    get_mcp_gateway,
)
from app.infrastructure.database import async_session_factory, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.execution_model import ExecutionModel  # noqa: E402
from app.models.server_model import ServerModel  # noqa: E402
from app.models.tool_model import ToolModel  # noqa: E402


@pytest.fixture(autouse=True)
async def cleanup_dependencies():
    """Ensure clean state before and after each test."""
    await init_db()
    yield
    # Cleanup state
    await _connection_manager.shutdown()

    if hasattr(_server_repo, "_servers"):
        _server_repo._servers.clear()
    else:
        async with async_session_factory() as session:
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


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
