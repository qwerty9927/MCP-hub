"""APScheduler setup for the hub's background jobs.

One AsyncIOScheduler per process, started and shut down in the FastAPI lifespan (app/main.py). Jobs are
defined in code and added on every start, so the in-memory job store is enough. Every job must be safe to
run on several hub instances at once.
"""

from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.background_service.session_sweeper import SessionSweeperService
from app.core.constants.session_constants import SESSION_SWEEP_CRON, SESSION_SWEEP_JOB_ID, SESSION_SWEEP_MISFIRE_GRACE_SECONDS


def create_scheduler(session_sweeper: SessionSweeperService) -> AsyncIOScheduler:
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
    return scheduler
