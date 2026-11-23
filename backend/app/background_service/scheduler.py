"""APScheduler setup for the hub's background jobs.

One AsyncIOScheduler per process, started and shut down in the FastAPI lifespan (app/main.py). Jobs are
defined in code and added on every start, so the in-memory job store is enough. Every job must be safe to
run on several hub instances at once.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.background_service.embedding_backfill import EmbeddingBackfillService
from app.background_service.session_sweeper import SessionSweeperService
from app.core.constants.auth_constants import (
    REFRESH_TOKEN_PURGE_INTERVAL_MINUTES,
    REFRESH_TOKEN_PURGE_JOB_ID,
    REFRESH_TOKEN_PURGE_MISFIRE_GRACE_SECONDS,
)
from app.core.constants.session_constants import SESSION_SWEEP_CRON, SESSION_SWEEP_JOB_ID, SESSION_SWEEP_MISFIRE_GRACE_SECONDS
from app.core.constants.tool_search_constants import (
    EMBEDDING_BACKFILL_INTERVAL_MINUTES,
    EMBEDDING_BACKFILL_JOB_ID,
    EMBEDDING_BACKFILL_MISFIRE_GRACE_SECONDS,
)


def create_scheduler(
    session_sweeper: SessionSweeperService,
    embedding_backfill: EmbeddingBackfillService,
    purge_refresh_tokens: Callable[[], Awaitable[int]],
) -> AsyncIOScheduler:
    """Build the scheduler with its jobs registered. Not started: call `start()` inside a running event loop."""
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        session_sweeper.complete_idle_sessions,
        trigger=CronTrigger(**SESSION_SWEEP_CRON, timezone=UTC),
        id=SESSION_SWEEP_JOB_ID,
        name="Complete idle sessions",
        max_instances=1,  # a slow sweep never overlaps the next one
        coalesce=True,  # runs missed while the loop was busy collapse into one
        misfire_grace_time=SESSION_SWEEP_MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    scheduler.add_job(
        embedding_backfill.backfill_embeddings,
        trigger=IntervalTrigger(minutes=EMBEDDING_BACKFILL_INTERVAL_MINUTES, timezone=UTC),
        id=EMBEDDING_BACKFILL_JOB_ID,
        name="Embed tools that have no embedding",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=EMBEDDING_BACKFILL_MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    scheduler.add_job(
        purge_refresh_tokens,  # AuthService.purge_expired_refresh_tokens (ADR-0009): one idempotent DELETE
        trigger=IntervalTrigger(minutes=REFRESH_TOKEN_PURGE_INTERVAL_MINUTES, timezone=UTC),
        id=REFRESH_TOKEN_PURGE_JOB_ID,
        name="Delete expired console refresh tokens",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=REFRESH_TOKEN_PURGE_MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    return scheduler
