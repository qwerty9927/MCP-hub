"""APScheduler setup for the hub's background jobs.

One AsyncIOScheduler per process, started and shut down in the FastAPI lifespan (app/main.py). Jobs are
defined in code and added on every start, so the in-memory job store is enough. Every job must be safe to
run on several hub instances at once.
"""

import functools
import time
from collections.abc import Awaitable, Callable
from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.background_service.embedding_backfill import EmbeddingBackfillService
from app.background_service.session_sweeper import SessionSweeperService
from app.core.config import Settings
from app.core.logging import logger
from app.services.auth_service import AuthService


def logged_job(job_id: str, func: Callable[[], Awaitable[int]], *, trigger: str = "scheduled") -> Callable[[], Awaitable[int]]:
    """`func` with a log line when each run starts and when it ends (with its duration and result).

    Jobs never raise by contract; a run that does anyway (or is cancelled at shutdown) is logged and re-raised.
    """

    @functools.wraps(func)
    async def run() -> int:
        logger.info(f"Job '{job_id}' started ({trigger})")
        started = time.monotonic()
        try:
            result = await func()
        except BaseException as exc:
            logger.warning(f"Job '{job_id}' stopped after {time.monotonic() - started:.2f}s: {type(exc).__name__}")
            raise
        logger.info(f"Job '{job_id}' finished in {time.monotonic() - started:.2f}s (result: {result})")
        return result

    return run


def create_scheduler(
    settings: Settings,
    session_sweeper: SessionSweeperService,
    embedding_backfill: EmbeddingBackfillService,
    auth_service: AuthService,
) -> AsyncIOScheduler:
    """Build the scheduler with its jobs registered, each scheduled from `settings`. Not started: call `start()` inside a running event loop."""
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        logged_job(settings.SESSION_SWEEP_JOB_ID, session_sweeper.complete_idle_sessions),
        trigger=CronTrigger(**settings.SESSION_SWEEP_CRON, timezone=UTC),
        id=settings.SESSION_SWEEP_JOB_ID,
        name="Complete idle sessions",
        max_instances=1,  # a slow sweep never overlaps the next one
        coalesce=True,  # runs missed while the loop was busy collapse into one
        misfire_grace_time=settings.SESSION_SWEEP_MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    scheduler.add_job(
        logged_job(settings.EMBEDDING_BACKFILL_JOB_ID, embedding_backfill.backfill_embeddings),
        trigger=IntervalTrigger(minutes=settings.EMBEDDING_BACKFILL_INTERVAL_MINUTES, timezone=UTC),
        id=settings.EMBEDDING_BACKFILL_JOB_ID,
        name="Embed tools that have no embedding",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.EMBEDDING_BACKFILL_MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    scheduler.add_job(
        # AuthService.purge_expired_refresh_tokens (ADR-0009): one idempotent DELETE
        logged_job(settings.REFRESH_TOKEN_PURGE_JOB_ID, auth_service.purge_expired_refresh_tokens),
        trigger=IntervalTrigger(minutes=settings.REFRESH_TOKEN_PURGE_INTERVAL_MINUTES, timezone=UTC),
        id=settings.REFRESH_TOKEN_PURGE_JOB_ID,
        name="Delete expired console refresh tokens",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.REFRESH_TOKEN_PURGE_MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    return scheduler
