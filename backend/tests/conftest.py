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

import app.api.dependencies as dependencies_module  # noqa: E402
import app.infrastructure.database as db_module  # noqa: E402
from app.api.dependencies import _connection_manager  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.api_key_model import ApiKeyModel  # noqa: E402
from app.models.execution_model import ExecutionModel  # noqa: E402
from app.models.server_model import ServerModel  # noqa: E402
from app.models.session_model import SessionModel  # noqa: E402
from app.models.tool_model import ToolModel  # noqa: E402
from app.models.user_model import UserModel  # noqa: E402
from tests.fake_embeddings import FakeEmbeddingService  # noqa: E402

# Every service built through app.api.dependencies embeds with the fake: no model download in tests.
dependencies_module._embedding_service = FakeEmbeddingService()

# Configure test engine with NullPool to prevent event loop cross-task issues in pytest-asyncio.
# Allows overriding DATABASE_URL with TEST_DATABASE_URL to protect local development data.
_settings = get_settings()
_test_db_url = os.environ.get("TEST_DATABASE_URL", "")
db_module.engine = db_module.create_database_engine(_test_db_url, poolclass=NullPool)
db_module.async_session_factory = async_sessionmaker(
    bind=db_module.engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


DEFAULT_PASSWORD = "test-password-123"


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
        await session.execute(delete(ApiKeyModel))
        await session.execute(delete(UserModel))
        await session.commit()

    await db_module.engine.dispose()


async def login_headers(client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    """Register `email` (if needed) and return an Authorization header for its console token."""
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
async def anon_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to the FastAPI application, with no credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client signed in as the default test account (owner@test.local)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.headers.update(await login_headers(client, "owner@test.local"))
        yield client


@pytest.fixture
async def other_user_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client signed in as a second, unrelated account."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.headers.update(await login_headers(client, "intruder@test.local"))
        yield client


@pytest.fixture
async def user_id(async_client: AsyncClient):
    """Account ID of the default test account."""
    from uuid import UUID

    return UUID((await async_client.get("/api/v1/auth/me")).json()["id"])


@pytest.fixture
async def account_id():
    """A stored account for tests that write owned rows straight through the repositories (no HTTP login)."""
    from uuid import uuid4

    from app.domain.user_entity import UserEntity
    from app.infrastructure.repositories.user_repository import PostgresUserRepository

    user = await PostgresUserRepository().create(UserEntity(email=f"{uuid4().hex[:12]}@test.local", password_hash="x"))
    return user.id
