"""Unit tests for the background job that embeds Tools stored without an embedding."""

from unittest.mock import MagicMock
from uuid import uuid4

from apscheduler.triggers.interval import IntervalTrigger

from app.background_service.embedding_backfill import EmbeddingBackfillService
from app.background_service.scheduler import create_scheduler
from app.core.config import get_settings
from app.domain.tool_entity import ToolEntity
from tests.fake_embeddings import FailingEmbeddingService, FakeEmbeddingService

USER_ID = uuid4()  # owner for entities in these mock-only tests
BATCH = get_settings().EMBEDDING_BACKFILL_BATCH


class InMemoryTools:
    """Just the two repository calls the backfill uses."""

    def __init__(self, count: int) -> None:
        self.pending = [
            ToolEntity(id=uuid4(), server_id=uuid4(), server_name="srv", name=f"tool_{i}", input_schema={}, user_id=USER_ID)
            for i in range(count)
        ]
        self.stored: dict = {}
        self.batch_sizes: list[int] = []

    async def list_tools_without_embedding(self, limit: int) -> list[ToolEntity]:
        return self.pending[:limit]

    async def set_embeddings(self, embeddings: dict) -> None:
        self.stored.update(embeddings)
        self.batch_sizes.append(len(embeddings))
        self.pending = [tool for tool in self.pending if tool.id not in embeddings]


async def test_embeds_every_pending_tool_in_batches():
    tools = InMemoryTools(BATCH + 3)

    embedded = await EmbeddingBackfillService(tools, FakeEmbeddingService(), BATCH).backfill_embeddings()

    assert embedded == BATCH + 3
    assert tools.batch_sizes == [BATCH, 3]
    assert tools.pending == []
    assert all(len(vector) == FakeEmbeddingService().dimension for vector in tools.stored.values())


async def test_nothing_pending_does_nothing():
    tools = InMemoryTools(0)
    assert await EmbeddingBackfillService(tools, FakeEmbeddingService(), BATCH).backfill_embeddings() == 0
    assert tools.batch_sizes == []


async def test_a_failing_model_is_logged_not_raised():
    tools = InMemoryTools(2)

    assert await EmbeddingBackfillService(tools, FailingEmbeddingService(), BATCH).backfill_embeddings() == 0
    assert len(tools.pending) == 2  # retried on the next run


async def test_scheduler_registers_the_backfill_as_a_non_overlapping_interval_job():
    settings = get_settings()
    backfill = EmbeddingBackfillService(InMemoryTools(0), FakeEmbeddingService(), BATCH)
    scheduler = create_scheduler(settings, MagicMock(), backfill, MagicMock())

    job = scheduler.get_job(settings.EMBEDDING_BACKFILL_JOB_ID)
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.max_instances == 1 and job.coalesce is True
    assert job.trigger.interval.total_seconds() == settings.EMBEDDING_BACKFILL_INTERVAL_MINUTES * 60
    assert job.misfire_grace_time == settings.EMBEDDING_BACKFILL_MISFIRE_GRACE_SECONDS
    assert job.func.__wrapped__ == backfill.backfill_embeddings  # wrapped by logged_job
