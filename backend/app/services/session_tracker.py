"""Session tracking for upstream MCP clients.

`/mcp` is stateless (ADR-0004): no request carries a transport session, so the hub derives every Session.
Requests from the same account, API key and client belong to one Session until it has been idle for
SESSION_IDLE_SECONDS. The client is its name + version when the request says (2026-07-28 `_meta`), else
its User-Agent. See docs/adr/0003-session-identity-without-transport-sessions.md.
"""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.core.enums.session_enum import SessionStatus
from app.core.logging import logger
from app.domain.principal_entity import Principal
from app.domain.session_entity import SessionEntity
from app.infrastructure.repositories.session_repository import SessionRepositoryAbstract

# An idle window approximating "one working session" for clients that never say when they start or stop.
SESSION_IDLE_SECONDS = 30 * 60

# A reused derived Session's last_activity_at is refreshed at most this often.
_ACTIVITY_REFRESH = timedelta(seconds=60)

# Older rows may still say "transport" (handshake-era sessions from before ADR-0004).
SOURCE_DERIVED = "derived"

_MAX_USER_AGENT_LENGTH = 255


@dataclass(frozen=True)
class ClientIdentity:
    """What a request says about the client that sent it."""

    name: str | None = None
    version: str | None = None
    protocol_version: str | None = None
    user_agent: str | None = None

    @property
    def label(self) -> str | None:
        """A short human-readable name: the client's own name, else the product part of its User-Agent."""
        if self.name:
            return self.name
        if self.user_agent:
            return self.user_agent.split(" ", 1)[0][:100]
        return None


class SessionTrackerService:
    """Maps each upstream MCP request to the hub Session it belongs to."""

    def __init__(self, session_repository: SessionRepositoryAbstract) -> None:
        self._sessions = session_repository
        self._locks: dict[str, asyncio.Lock] = {}

    async def resolve(self, principal: Principal, client: ClientIdentity) -> str | None:
        """Return the Session ID for this request, opening a Session if needed; None if none can be attributed.

        Never raises: losing Session attribution must not fail the agent's request.
        """
        try:
            return await self._derived_session(principal, client)
        except Exception as exc:
            logger.warning(f"Could not attribute MCP request to a session: {exc}")
            return None

    async def _derived_session(self, principal: Principal, client: ClientIdentity) -> str:
        fingerprint = client_fingerprint(principal, client)
        # Serialise per client so concurrent first requests do not each open a Session.
        lock = self._locks.setdefault(fingerprint, asyncio.Lock())
        async with lock:
            now = datetime.now(UTC)
            current = await self._sessions.find_active_by_fingerprint(principal.user_id, fingerprint)
            if current is not None:
                idle = now - current.last_activity_at
                if idle <= timedelta(seconds=SESSION_IDLE_SECONDS):
                    if idle > _ACTIVITY_REFRESH:
                        await self._sessions.update_activity(current.id, now)
                    return current.id
                await self._sessions.update_status(current.id, SessionStatus.COMPLETED, owner_id=principal.user_id)

            session_id = uuid4().hex
            await self._sessions.create(
                SessionEntity(
                    id=session_id,
                    title=f"{client.label or 'MCP client'} ({session_id[:8]})",
                    status=SessionStatus.ACTIVE,
                    metadata=_metadata(client),
                    created_at=now,
                    last_activity_at=now,
                    owner_id=principal.user_id,
                    api_key_id=principal.api_key_id,
                    client_fingerprint=fingerprint,
                )
            )
            logger.info(f"Opened derived session {session_id[:8]} for account {principal.user_id}")
            return session_id


def client_fingerprint(principal: Principal, client: ClientIdentity) -> str:
    """Stable key for "the same client of the same account, on the same API key".

    A client that names itself is keyed on name + version (unchanged from ADR-0003); one that does not
    (a handshake-era client, whose `initialize` a stateless server forgets) is keyed on its User-Agent.
    """
    if client.name:
        client_key = (client.name, client.version or "unknown")
    elif client.user_agent:
        client_key = ("ua", client.user_agent)
    else:
        client_key = ("unknown", "unknown")
    parts = (str(principal.user_id), str(principal.api_key_id or ""), *client_key)
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _metadata(client: ClientIdentity) -> dict[str, Any]:
    metadata: dict[str, Any] = {"session_source": SOURCE_DERIVED}
    if client.name:
        metadata["client_name"] = client.name
    if client.version:
        metadata["client_version"] = client.version
    if client.protocol_version:
        metadata["protocol_version"] = client.protocol_version
    if client.user_agent:
        metadata["user_agent"] = client.user_agent[:_MAX_USER_AGENT_LENGTH]
    return metadata
