"""Background job: complete hub Sessions that have gone idle (ADR-0005).

The Session tracker only ends an idle Session when the same client calls again. A client that stops calling
would leave its Session `active` for ever; this job, run on a schedule by app/background_service/scheduler.py,
completes such Sessions once they pass their idle timeout.
"""

from datetime import UTC, datetime

from app.core.constants.session_constants import DEFAULT_SESSION_IDLE_SECONDS
from app.core.logging import logger
from app.infrastructure.repositories.session_repository import SessionRepositoryAbstract


class SessionSweeperService:
    """Completes every active Session idle for longer than its own timeout (or the default)."""

    def __init__(self, session_repository: SessionRepositoryAbstract) -> None:
        self._session_repository = session_repository

    async def complete_idle_sessions(self) -> int:
        """Run one sweep; returns how many Sessions were completed.

        Never raises: a failed sweep is logged and the scheduler runs the next one on time.
        """
        try:
            completed = await self._session_repository.complete_idle_sessions(datetime.now(UTC), DEFAULT_SESSION_IDLE_SECONDS)
        except Exception as exc:
            logger.error(f"Could not complete idle sessions: {exc}")
            return 0
        if completed:
            logger.info(f"Completed {completed} idle session(s)")
        return completed
