"""Unit tests for attributing MCP requests to hub Sessions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.enums.session_enum import SessionStatus
from app.domain.api_key_entity import ApiKeyEntity
from app.domain.principal_entity import Principal
from app.domain.user_entity import UserEntity
from app.infrastructure.repositories.api_key_repository import PostgresApiKeyRepository
from app.infrastructure.repositories.session_repository import PostgresSessionRepository
from app.infrastructure.repositories.user_repository import PostgresUserRepository
from app.services.session_tracker import SESSION_IDLE_SECONDS, ClientIdentity, SessionTracker, client_fingerprint

CLIENT = ClientIdentity(name="claude-code", version="2.0.0", protocol_version="2026-07-28")


@pytest.fixture
def repo() -> PostgresSessionRepository:
    return PostgresSessionRepository()


@pytest.fixture
def tracker(repo) -> SessionTracker:
    return SessionTracker(repo)


async def _principal(email: str, with_key: bool = True) -> Principal:
    user = await PostgresUserRepository().create(UserEntity(email=email, password_hash="x"))
    if not with_key:
        return Principal(user_id=user.id)
    key = await PostgresApiKeyRepository().create(ApiKeyEntity(user_id=user.id, name="k", key_prefix="mhk_", key_hash=uuid4().hex))
    return Principal(user_id=user.id, api_key_id=key.id)


async def test_same_client_reuses_one_derived_session(tracker, repo):
    principal = await _principal("a@test.local")

    first = await tracker.resolve(principal, None, CLIENT)
    second = await tracker.resolve(principal, None, CLIENT)

    assert first is not None and first == second
    detail = await repo.get_by_id(first, owner_id=principal.user_id)
    assert detail.metadata["session_source"] == "derived"
    assert detail.metadata["client_name"] == "claude-code"


async def test_idle_session_is_completed_and_replaced(tracker, repo):
    principal = await _principal("b@test.local")
    first = await tracker.resolve(principal, None, CLIENT)
    stale = datetime.now(UTC) - timedelta(seconds=SESSION_IDLE_SECONDS + 5)
    await repo.update_activity(first, stale)

    second = await tracker.resolve(principal, None, CLIENT)

    assert second != first
    assert (await repo.get_by_id(first)).status == SessionStatus.COMPLETED


async def test_different_api_keys_and_clients_get_different_sessions(tracker):
    principal = await _principal("c@test.local")
    other_key = Principal(user_id=principal.user_id, api_key_id=(await _principal("c2@test.local")).api_key_id)

    base = await tracker.resolve(principal, None, CLIENT)
    other_client = await tracker.resolve(principal, None, ClientIdentity(name="cursor", version="1.0"))

    assert base != other_client
    assert client_fingerprint(principal, CLIENT) != client_fingerprint(other_key, CLIENT)


async def test_accounts_never_share_a_session(tracker):
    alice = await _principal("alice@test.local", with_key=False)
    bob = await _principal("bob@test.local", with_key=False)

    assert await tracker.resolve(alice, None, CLIENT) != await tracker.resolve(bob, None, CLIENT)


async def test_concurrent_first_requests_open_one_session(tracker):
    import asyncio

    principal = await _principal("d@test.local")

    ids = await asyncio.gather(*(tracker.resolve(principal, None, CLIENT) for _ in range(5)))

    assert len(set(ids)) == 1


async def test_transport_session_id_wins_and_is_owned(tracker, repo):
    principal = await _principal("e@test.local")

    session_id = await tracker.resolve(principal, "transport-123", CLIENT)

    assert session_id == "transport-123"
    detail = await repo.get_by_id("transport-123", owner_id=principal.user_id)
    assert detail.metadata["session_source"] == "transport"


async def test_foreign_transport_session_is_not_attributed(tracker):
    owner = await _principal("f@test.local")
    intruder = await _principal("g@test.local")
    await tracker.resolve(owner, "shared-id", CLIENT)

    assert await tracker.resolve(intruder, "shared-id", CLIENT) is None


async def test_repository_failure_never_raises():
    class Broken(PostgresSessionRepository):
        async def find_active_by_fingerprint(self, owner_id, fingerprint):
            raise RuntimeError("db down")

    principal = Principal(user_id=uuid4())

    assert await SessionTracker(Broken()).resolve(principal, None, CLIENT) is None
