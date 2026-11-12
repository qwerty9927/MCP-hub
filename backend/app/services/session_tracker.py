"""Session tracking for upstream MCP clients, with or without a transport session.

Clients on the handshake protocol revisions open a transport session (`Mcp-Session-Id`), which becomes the
hub's Session as before. Clients on 2026-07-28 send self-contained requests with no session at all, so the
hub derives one: requests from the same account, API key and client (name + version) belong to one Session
until it has been idle for SESSION_IDLE_SECONDS. See docs/adr/0003-session-identity-without-transport-sessions.md.
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

# Mirrors the MCP SDK's own idle timeout for stateful Streamable HTTP sessions.
SESSION_IDLE_SECONDS = 30 * 60

# A reused derived Session's last_activity_at is refreshed at most this often.
_ACTIVITY_REFRESH = timedelta(seconds=60)

SOURCE_TRANSPORT = "transport"
SOURCE_DERIVED = "derived"


@dataclass(frozen=True)
class ClientIdentity:
    """What a request says about the client that sent it."""

    name: str | None = None
    version: str | None = None
    protocol_version: str | None = None


def client_fingerprint(principal: Principal, client: ClientIdentity) -> str:
    """Stable key for "the same client of the same account, on the same API key"."""
    parts = (str(principal.user_id), str(principal.api_key_id or ""), client.name or "unknown", client.version or "unknown")
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class SessionTracker:
    """Maps each upstream MCP request to the hub Session it belongs to."""

    def __init__(self, session_repository: SessionRepositoryAbstract) -> None:
        self._sessions = session_repository
        self._locks: dict[str, asyncio.Lock] = {}

    async def resolve(self, principal: Principal, transport_session_id: str | None, client: ClientIdentity) -> str | None:
        """Return the Session ID for this request, creating the Session if needed; None if none can be attributed.

        Never raises: losing Session attribution must not fail the agent's request.
        """
        try:
            if transport_session_id:
                return await self._transport_session(principal, transport_session_id, client)
            return await self._derived_session(principal, client)
        except Exception as exc:
            logger.warning(f"Could not attribute MCP request to a session: {exc}")
            return None

    async def _transport_session(self, principal: Principal, session_id: str, client: ClientIdentity) -> str | None:
        session = await self._sessions.get_or_create(
            session_id=session_id,
            owner_id=principal.user_id,
            api_key_id=principal.api_key_id,
            title=f"{client.name} ({session_id[:8]})" if client.name else None,
            metadata=_metadata(client, SOURCE_TRANSPORT),
        )
        if session is None:
            logger.warning(f"Transport session '{session_id[:8]}' belongs to another account; not attributing")
            return None
        return session.id

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
                    title=f"{client.name or 'MCP client'} ({session_id[:8]})",
                    status=SessionStatus.ACTIVE,
                    metadata=_metadata(client, SOURCE_DERIVED),
                    created_at=now,
                    last_activity_at=now,
                    owner_id=principal.user_id,
                    api_key_id=principal.api_key_id,
                    client_fingerprint=fingerprint,
                )
            )
            logger.info(f"Opened derived session {session_id[:8]} for account {principal.user_id}")
            return session_id


def _metadata(client: ClientIdentity, source: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {"session_source": source}
    if client.name:
        metadata["client_name"] = client.name
    if client.version:
        metadata["client_version"] = client.version
    if client.protocol_version:
        metadata["protocol_version"] = client.protocol_version
    return metadata
