"""Unit tests for the background job that completes idle Sessions (app/background_service/)."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apscheduler.triggers.cron import CronTrigger

from app.background_service.scheduler import create_scheduler
from app.background_service.session_sweeper import SessionSweeperService
from app.core.constants.session_constants import DEFAULT_SESSION_IDLE_SECONDS, SESSION_SWEEP_JOB_ID
from app.core.enums.session_enum import SessionStatus
from app.domain.session_entity import SessionEntity
from app.infrastructure.repositories.session_repository import PostgresSessionRepository


async def _session(
    repo: PostgresSessionRepository, idle_for: timedelta, status=SessionStatus.ACTIVE, timeout: int | None = None, *, account_id
) -> str:
    last_activity = datetime.now(UTC) - idle_for
    created = await repo.create(
        SessionEntity(
            id=uuid4(),
            status=status,
            created_at=last_activity,
            last_activity_at=last_activity,
            idle_timeout_seconds=timeout,
            user_id=account_id,
        )
    )
    return created.id


async def test_completes_only_active_sessions_idle_past_their_timeout(account_id):
    repo = PostgresSessionRepository()
    past_default = await _session(repo, timedelta(seconds=DEFAULT_SESSION_IDLE_SECONDS + 60), account_id=account_id)
    past_own = await _session(repo, timedelta(seconds=120), timeout=60, account_id=account_id)
    within_own = await _session(repo, timedelta(seconds=120), timeout=3600, account_id=account_id)
    recent_default = await _session(repo, timedelta(seconds=30), account_id=account_id)
    already_completed = await _session(repo, timedelta(days=2), status=SessionStatus.COMPLETED, account_id=account_id)
    failed = await _session(repo, timedelta(days=2), status=SessionStatus.FAILED, account_id=account_id)
    before = (await repo.get_by_id(past_own, user_id=account_id)).last_activity_at

    completed = await SessionSweeperService(repo).complete_idle_sessions()

    assert completed == 2
    status = {
        sid: (await repo.get_by_id(sid, user_id=account_id)).status
        for sid in (past_default, past_own, within_own, recent_default, already_completed, failed)
    }
    assert status == {
        past_default: SessionStatus.COMPLETED,
        past_own: SessionStatus.COMPLETED,
        within_own: SessionStatus.ACTIVE,
        recent_default: SessionStatus.ACTIVE,
        already_completed: SessionStatus.COMPLETED,
        failed: SessionStatus.FAILED,
    }
    # The sweep must not rewrite when the agent last acted.
    assert (await repo.get_by_id(past_own, user_id=account_id)).last_activity_at == before

    # Idempotent: a second sweep finds nothing new.
    assert await SessionSweeperService(repo).complete_idle_sessions() == 0


async def test_sweep_failure_is_logged_not_raised():
    class Broken(PostgresSessionRepository):
        async def complete_idle_sessions(self, now, default_idle_seconds):
            raise RuntimeError("db down")

    assert await SessionSweeperService(Broken()).complete_idle_sessions() == 0


async def test_scheduler_registers_one_non_overlapping_cron_job():
    scheduler = create_scheduler(SessionSweeperService(PostgresSessionRepository()))

    jobs = scheduler.get_jobs()
    assert [job.id for job in jobs] == [SESSION_SWEEP_JOB_ID]
    job = jobs[0]
    assert isinstance(job.trigger, CronTrigger)
    assert job.max_instances == 1 and job.coalesce is True

    scheduler.start()
    try:
        assert scheduler.running
        assert scheduler.get_job(SESSION_SWEEP_JOB_ID).next_run_time is not None
    finally:
        scheduler.shutdown(wait=False)
    await asyncio.sleep(0)  # AsyncIOScheduler finishes stopping on the next event-loop tick
    assert not scheduler.running
