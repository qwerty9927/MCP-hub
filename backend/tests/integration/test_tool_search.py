"""SEARCH_TOOLS vector search in pgvector (ADR-0006), against the database with the fake embedder."""

import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import event, select, text, update

import app.infrastructure.database as db_module
from app.api.dependencies import get_tool_catalog_service
from app.background_service.embedding_backfill import EmbeddingBackfillService
from app.domain.server_entity import ServerEntity, TransportType
from app.domain.tool_entity import ToolEntity
from app.domain.user_entity import UserEntity
from app.infrastructure.repositories.server_repository import PostgresServerRepository
from app.infrastructure.repositories.tool_repository import PostgresToolRepository
from app.infrastructure.repositories.user_repository import PostgresUserRepository
from app.models.tool_model import ToolModel
from app.services.embedding_service import FastEmbedService, normalize
from app.services.tool_catalog import ToolCatalogService
from tests.fake_embeddings import FailingEmbeddingService, FakeEmbeddingService

DEMO_SERVER = str(Path(__file__).resolve().parent.parent.parent / "demo_server" / "server.py")


async def connected_demo_server(client: AsyncClient) -> str:
    server = (
        await client.post(
            "/api/v1/servers",
            json={"name": "math", "transport": "stdio", "stdio_config": {"command": sys.executable, "args": [DEMO_SERVER]}},
        )
    ).json()
    assert (await client.post(f"/api/v1/servers/{server['id']}/refresh-tools")).status_code == 200
    return server["id"]


async def search(queries: list[str], user_id: UUID, top_k: int = 5) -> list[list[tuple[ToolEntity, float]]]:
    return await get_tool_catalog_service().search(queries, user_id=user_id, top_k=top_k)


async def test_discovery_embeds_tools_and_search_ranks_the_best_match_first(async_client, user_id):
    await connected_demo_server(async_client)

    [ranked] = await search(["calculate a math expression"], user_id)

    assert ranked[0][0].name == "calculate"
    similarities = [similarity for _, similarity in ranked]
    assert similarities == sorted(similarities, reverse=True)
    assert all(-1.0 <= s <= 1.0 for s in similarities)


async def test_top_k_limits_each_query(async_client, user_id):
    await connected_demo_server(async_client)

    one, three = await search(["echo message"], user_id, top_k=1), await search(["echo message"], user_id, top_k=3)

    assert [t.name for t, _ in one[0]] == ["echo"]
    assert len(three[0]) == 3


async def test_another_account_finds_none_of_my_tools(async_client, other_user_client, user_id):
    await connected_demo_server(async_client)
    other_id = UUID((await other_user_client.get("/api/v1/auth/me")).json()["id"])

    assert await search(["calculate"], other_id) == [[]]


async def test_disabled_server_and_unavailable_tools_are_not_searched(async_client, user_id):
    server_id = await connected_demo_server(async_client)
    async with db_module.async_session_factory() as session:
        await session.execute(update(ToolModel).where(ToolModel.name == "echo").values(availability_status="UNAVAILABLE"))
        await session.commit()

    assert "echo" not in {t.name for t, _ in (await search(["echo message"], user_id))[0]}

    assert (await async_client.patch(f"/api/v1/servers/{server_id}", json={"enabled": False})).status_code == 200
    assert await search(["calculate"], user_id) == [[]]


async def test_failed_embedding_keeps_discovery_working_and_backfill_fills_it_in(account_id):
    server = await PostgresServerRepository().create(
        ServerEntity(id=uuid4(), name="math", transport=TransportType.STDIO, user_id=account_id)
    )
    tool = ToolEntity(id=uuid4(), server_id=server.id, server_name="math", name="calculate", input_schema={}, user_id=account_id)
    failing = ToolCatalogService(tool_repository=PostgresToolRepository(), embedding_service=FailingEmbeddingService())
    await PostgresToolRepository().replace_server_tools(server.id, "math", [tool], await failing._embed_tools([tool]))

    async with db_module.async_session_factory() as session:
        assert (await session.execute(select(ToolModel.embedding).where(ToolModel.id == str(tool.id)))).scalar_one() is None

    backfill = EmbeddingBackfillService(tool_repository=PostgresToolRepository(), embedding_service=FakeEmbeddingService())
    assert await backfill.backfill_embeddings() == 1
    assert await backfill.backfill_embeddings() == 0
    catalog = ToolCatalogService(tool_repository=PostgresToolRepository(), embedding_service=FakeEmbeddingService())
    [ranked] = await catalog.search(["calculate"], user_id=account_id, top_k=5)
    assert [t.id for t, _ in ranked] == [tool.id]


@pytest.fixture
async def force_hnsw_index():
    """Make the planner scan the HNSW index even on this tiny table, as it would on a large one.

    Without these it picks a btree index and sorts, which is exact and hides the bug. The VACUUM first clears the
    dead index entries left by earlier tests' DELETEs, which would otherwise use up the index scan's work budget.
    """
    async with db_module.engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.execute(text("VACUUM discovered_tools"))

    def prefer_ordered_index_scans(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET enable_seqscan = off")
        cursor.execute("SET enable_sort = off")
        cursor.close()

    event.listen(db_module.engine.sync_engine, "connect", prefer_ordered_index_scans)
    yield
    event.remove(db_module.engine.sync_engine, "connect", prefer_ordered_index_scans)


async def store_tools_near(user: UUID, server_name: str, count: int, query: list[float], spread: float, rng) -> list[ToolEntity]:
    """`count` Tools whose embeddings are `query` nudged by `spread` in random directions (distinct, like real ones).

    Identical vectors would share HNSW graph elements and so not fill `hnsw.ef_search`.
    """
    server = await PostgresServerRepository().create(
        ServerEntity(id=uuid4(), name=server_name, transport=TransportType.STDIO, user_id=user)
    )
    tools = [
        ToolEntity(id=uuid4(), server_id=server.id, server_name=server_name, name=f"tool_{i}", input_schema={}, user_id=user)
        for i in range(count)
    ]
    vectors = []
    for _ in tools:
        noise = rng.standard_normal(len(query))
        vectors.append(normalize(np.asarray(query) + spread * noise / np.linalg.norm(noise)))
    await PostgresToolRepository().replace_server_tools(server.id, server_name, tools, vectors)
    return tools


async def test_search_fills_top_k_when_other_accounts_crowd_the_index(account_id, force_hnsw_index):
    """Filters must not cut results short: the index scan goes past its first `hnsw.ef_search` (40) candidates."""
    other_id = (await PostgresUserRepository().create(UserEntity(email=f"{uuid4().hex[:12]}@test.local", password_hash="x"))).id
    fake = FakeEmbeddingService()
    query = await fake.embed_query("calculate expression")
    rng = np.random.default_rng(7)
    # Another account's 100 Tools are all nearer the query than any of mine.
    await store_tools_near(other_id, "crowd", 100, query, spread=0.5, rng=rng)
    mine = await store_tools_near(account_id, "math", 3, query, spread=1.5, rng=rng)

    catalog = ToolCatalogService(tool_repository=PostgresToolRepository(), embedding_service=fake)
    [ranked] = await catalog.search(["calculate expression"], user_id=account_id, top_k=3)

    assert {t.id for t, _ in ranked} == {t.id for t in mine}
    similarities = [similarity for _, similarity in ranked]
    assert similarities == sorted(similarities, reverse=True)


@pytest.mark.skipif(os.environ.get("RUN_SLOW") != "1", reason="loads the real embedding model; set RUN_SLOW=1")
async def test_real_model_matches_by_meaning_not_words(account_id):
    """The point of vector search: 'open a ticket' finds create_issue though they share no words."""
    from app.core.config import get_settings

    settings = get_settings()
    model = FastEmbedService(settings.EMBEDDING_MODEL, settings.EMBEDDING_DIMENSION, settings.EMBEDDING_CACHE_DIR)
    catalog = ToolCatalogService(tool_repository=PostgresToolRepository(), embedding_service=model)
    server = await PostgresServerRepository().create(
        ServerEntity(id=uuid4(), name="work", transport=TransportType.STDIO, user_id=account_id)
    )
    tools = [
        ToolEntity(
            id=uuid4(), server_id=server.id, server_name="work", name=name, description=description, input_schema={}, user_id=account_id
        )
        for name, description in [
            ("create_issue", "Create a new issue in a GitHub repository"),
            ("send_email", "Send an email message to a recipient"),
            ("list_channels", "List the channels in a Slack workspace"),
        ]
    ]
    await PostgresToolRepository().replace_server_tools(server.id, "work", tools, await catalog._embed_tools(tools))

    [ranked] = await catalog.search(["open a ticket for a bug"], user_id=account_id, top_k=3)

    assert ranked[0][0].name == "create_issue"
