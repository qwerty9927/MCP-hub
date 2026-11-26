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


def logged_job(
    job_id: str,
    func: Callable[[], Awaitable[int]],
    *,
    unit: str = "item(s) processed",
    trigger: str = "scheduled",
) -> Callable[[], Awaitable[int]]:
    """`func` with a log line when each run starts and one when it finishes or fails, with its duration.

    `func` returns how many `unit` it handled. A job that raises is logged as failed (ERROR) and counts 0, so the
    scheduler keeps running it on time; cancellation at shutdown is logged and re-raised.
    """

    @functools.wraps(func)
    async def run() -> int:
        logger.info(f"Job '{job_id}' started ({trigger})")
        started = time.monotonic()
        try:
            result = await func()
        except Exception as exc:
            logger.error(f"Job '{job_id}' failed after {time.monotonic() - started:.2f}s: {type(exc).__name__}: {exc}")
            return 0
        except BaseException as exc:
            logger.warning(f"Job '{job_id}' stopped after {time.monotonic() - started:.2f}s: {type(exc).__name__}")
            raise
        logger.info(f"Job '{job_id}' finished in {time.monotonic() - started:.2f}s: {result} {unit}")
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
        logged_job(settings.SESSION_SWEEP_JOB_ID, session_sweeper.complete_idle_sessions, unit="idle session(s) completed"),
        trigger=CronTrigger(**settings.SESSION_SWEEP_CRON, timezone=UTC),
        id=settings.SESSION_SWEEP_JOB_ID,
        name="Complete idle sessions",
        max_instances=1,  # a slow sweep never overlaps the next one
        coalesce=True,  # runs missed while the loop was busy collapse into one
        misfire_grace_time=settings.SESSION_SWEEP_MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    scheduler.add_job(
        logged_job(settings.EMBEDDING_BACKFILL_JOB_ID, embedding_backfill.backfill_embeddings, unit="tool(s) embedded"),
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
        logged_job(settings.REFRESH_TOKEN_PURGE_JOB_ID, auth_service.purge_expired_refresh_tokens, unit="expired refresh token(s) deleted"),
        trigger=IntervalTrigger(minutes=settings.REFRESH_TOKEN_PURGE_INTERVAL_MINUTES, timezone=UTC),
        id=settings.REFRESH_TOKEN_PURGE_JOB_ID,
        name="Delete expired console refresh tokens",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.REFRESH_TOKEN_PURGE_MISFIRE_GRACE_SECONDS,
        replace_existing=True,
    )
    return scheduler
