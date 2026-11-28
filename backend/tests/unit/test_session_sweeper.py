"""Unit tests for the background job that completes idle Sessions (app/background_service/)."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.background_service.scheduler import create_scheduler
from app.background_service.session_sweeper import SessionSweeperService
from app.core.config import get_settings
from app.core.constants.auth_constants import AUTH_RATE_LIMIT_PURGE_JOB_ID
from app.core.constants.session_constants import DEFAULT_SESSION_IDLE_SECONDS
from app.core.enums.session_enum import SessionStatus
from app.domain.session_entity import SessionEntity
from app.infrastructure.repositories.session_repository import PostgresSessionRepository


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


async def test_a_sweep_failure_raises_for_the_job_wrapper_to_log():
    class Broken(PostgresSessionRepository):
        async def complete_idle_sessions(self, now, default_idle_seconds):
            raise RuntimeError("db down")

    with pytest.raises(RuntimeError, match="db down"):
        await SessionSweeperService(Broken()).complete_idle_sessions()


async def test_scheduler_registers_one_non_overlapping_cron_job():
    settings = get_settings()
    scheduler = create_scheduler(settings, SessionSweeperService(PostgresSessionRepository()), MagicMock(), MagicMock(), MagicMock())

    jobs = scheduler.get_jobs()
    assert {job.id for job in jobs} == {
        settings.SESSION_SWEEP_JOB_ID,
        settings.EMBEDDING_BACKFILL_JOB_ID,
        settings.REFRESH_TOKEN_PURGE_JOB_ID,
        AUTH_RATE_LIMIT_PURGE_JOB_ID,
    }
    job = scheduler.get_job(settings.SESSION_SWEEP_JOB_ID)
    assert isinstance(job.trigger, CronTrigger)
    assert job.max_instances == 1 and job.coalesce is True

    scheduler.start()
    try:
        assert scheduler.running
        assert scheduler.get_job(settings.SESSION_SWEEP_JOB_ID).next_run_time is not None
    finally:
        scheduler.shutdown(wait=False)
    await asyncio.sleep(0)  # AsyncIOScheduler finishes stopping on the next event-loop tick
    assert not scheduler.running


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


async def test_every_job_run_logs_its_start_and_end(caplog):
    from app.background_service.scheduler import logged_job

    async def job() -> int:
        return 3

    with caplog.at_level("INFO"):
        assert await logged_job("demo-job", job, unit="widget(s) polished")() == 3

    messages = [record.getMessage() for record in caplog.records]
    assert "Job 'demo-job' started (scheduled)" in messages
    assert any(m.startswith("Job 'demo-job' finished in ") and m.endswith(": 3 widget(s) polished") for m in messages)


async def test_a_failing_job_is_logged_as_failed_not_finished_and_counts_zero(caplog):
    from app.background_service.scheduler import logged_job

    async def job() -> int:
        raise RuntimeError("db down")

    with caplog.at_level("INFO"):
        assert await logged_job("demo-job", job, trigger="startup")() == 0  # the scheduler keeps running it

    by_message = {record.getMessage(): record.levelname for record in caplog.records}
    assert by_message["Job 'demo-job' started (startup)"] == "INFO"
    [failed] = [m for m in by_message if m.startswith("Job 'demo-job' failed after ")]
    assert failed.endswith(": RuntimeError: db down") and by_message[failed] == "ERROR"
    assert not any("finished" in m for m in by_message)


async def test_a_cancelled_job_is_logged_as_stopped_and_re_raised(caplog):
    from app.background_service.scheduler import logged_job

    async def job() -> int:
        raise asyncio.CancelledError

    with caplog.at_level("INFO"), pytest.raises(asyncio.CancelledError):
        await logged_job("demo-job", job)()

    assert any(r.getMessage().startswith("Job 'demo-job' stopped after ") and r.levelname == "WARNING" for r in caplog.records)


async def test_scheduled_jobs_are_wrapped_with_start_and_end_logs():
    settings = get_settings()
    sweeper = SessionSweeperService(PostgresSessionRepository())
    auth_service = MagicMock()
    scheduler = create_scheduler(settings, sweeper, MagicMock(), auth_service, MagicMock())

    assert scheduler.get_job(settings.SESSION_SWEEP_JOB_ID).func.__wrapped__ == sweeper.complete_idle_sessions
    assert scheduler.get_job(settings.REFRESH_TOKEN_PURGE_JOB_ID).func.__wrapped__ is auth_service.purge_expired_refresh_tokens
