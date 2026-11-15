"""Unit tests for attributing MCP requests to hub Sessions."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.constants.session_constants import DEFAULT_SESSION_IDLE_SECONDS
from app.core.enums.session_enum import SessionStatus
from app.domain.api_key_entity import ApiKeyEntity
from app.domain.principal_entity import Principal
from app.domain.user_entity import UserEntity
from app.infrastructure.repositories.api_key_repository import PostgresApiKeyRepository
from app.infrastructure.repositories.session_repository import PostgresSessionRepository
from app.infrastructure.repositories.user_repository import PostgresUserRepository
from app.services.session_tracker import ClientIdentity, SessionTrackerService, client_fingerprint

CLIENT = ClientIdentity(name="claude-code", version="2.0.0", protocol_version="2026-07-28")


@pytest.fixture
def repo() -> PostgresSessionRepository:
    return PostgresSessionRepository()


@pytest.fixture
def tracker(repo) -> SessionTrackerService:
    return SessionTrackerService(repo)


async def _principal(email: str, with_key: bool = True) -> Principal:
    user = await PostgresUserRepository().create(UserEntity(email=email, password_hash="x"))
    if not with_key:
        return Principal(user_id=user.id)
    key = await PostgresApiKeyRepository().create(ApiKeyEntity(user_id=user.id, name="k", key_prefix="mhk_", key_hash=uuid4().hex))
    return Principal(user_id=user.id, api_key_id=key.id)


async def test_same_client_reuses_one_derived_session(tracker, repo):
    principal = await _principal("a@test.local")

    first = await tracker.resolve(principal, CLIENT)
    second = await tracker.resolve(principal, CLIENT)

    assert first is not None and first == second
    assert str(UUID(first)) == first  # a dashed str(UUID), like every other id
    detail = await repo.get_by_id(first, user_id=principal.user_id)
    assert detail.metadata["session_source"] == "derived"
    assert detail.metadata["client_name"] == "claude-code"


async def test_idle_session_is_completed_and_replaced(tracker, repo):
    principal = await _principal("b@test.local")
    first = await tracker.resolve(principal, CLIENT)
    stale = datetime.now(UTC) - timedelta(seconds=DEFAULT_SESSION_IDLE_SECONDS + 5)
    await repo.update_activity(first, stale)

    second = await tracker.resolve(principal, CLIENT)

    assert second != first
    assert (await repo.get_by_id(first, user_id=principal.user_id)).status == SessionStatus.COMPLETED


async def test_different_api_keys_and_clients_get_different_sessions(tracker):
    principal = await _principal("c@test.local")
    other_key = Principal(user_id=principal.user_id, api_key_id=(await _principal("c2@test.local")).api_key_id)

    base = await tracker.resolve(principal, CLIENT)
    other_client = await tracker.resolve(principal, ClientIdentity(name="cursor", version="1.0"))

    assert base != other_client
    assert client_fingerprint(principal, CLIENT) != client_fingerprint(other_key, CLIENT)


async def test_accounts_never_share_a_session(tracker):
    alice = await _principal("alice@test.local", with_key=False)
    bob = await _principal("bob@test.local", with_key=False)

    assert await tracker.resolve(alice, CLIENT) != await tracker.resolve(bob, CLIENT)


async def test_concurrent_first_requests_open_one_session(tracker):
    import asyncio

    principal = await _principal("d@test.local")

    ids = await asyncio.gather(*(tracker.resolve(principal, CLIENT) for _ in range(5)))

    assert len(set(ids)) == 1


async def test_unnamed_clients_are_told_apart_by_user_agent(tracker, repo):
    """Handshake-era clients have no name on a stateless server, so their User-Agent keys the Session."""
    principal = await _principal("e@test.local")
    cursor = ClientIdentity(user_agent="Cursor/1.4 (darwin)")
    vscode = ClientIdentity(user_agent="VSCode/1.99")

    first = await tracker.resolve(principal, cursor)
    again = await tracker.resolve(principal, cursor)
    other = await tracker.resolve(principal, vscode)

    assert first == again != other
    detail = await repo.get_by_id(first, user_id=principal.user_id)
    assert detail.title.startswith("Cursor/1.4 (")
    assert detail.metadata == {"session_source": "derived", "user_agent": "Cursor/1.4 (darwin)"}


async def test_client_name_takes_precedence_over_user_agent():
    principal = Principal(user_id=uuid4(), api_key_id=uuid4())

    with_ua = ClientIdentity(name="claude-code", version="2.0.0", user_agent="node-fetch")
    without_ua = ClientIdentity(name="claude-code", version="2.0.0")

    assert client_fingerprint(principal, with_ua) == client_fingerprint(principal, without_ua)
    assert client_fingerprint(principal, ClientIdentity(user_agent="node-fetch")) != client_fingerprint(principal, without_ua)


async def test_repository_failure_never_raises():
    class Broken(PostgresSessionRepository):
        async def find_active_by_fingerprint(self, user_id, fingerprint):
            raise RuntimeError("db down")

    principal = Principal(user_id=uuid4())

    assert await SessionTrackerService(Broken()).resolve(principal, CLIENT) is None


async def test_new_session_snapshots_the_key_idle_timeout(tracker, repo):
    principal = await _principal("h@test.local")
    keyed = Principal(user_id=principal.user_id, api_key_id=principal.api_key_id, session_idle_seconds=300)
    unset = await _principal("i@test.local")

    custom = await tracker.resolve(keyed, CLIENT)
    default = await tracker.resolve(unset, CLIENT)

    assert (await repo.find_active_by_fingerprint(keyed.user_id, client_fingerprint(keyed, CLIENT))).id == custom
    custom_entity = await repo.find_active_by_fingerprint(keyed.user_id, client_fingerprint(keyed, CLIENT))
    default_entity = await repo.find_active_by_fingerprint(unset.user_id, client_fingerprint(unset, CLIENT))
    assert custom_entity.idle_timeout_seconds == 300
    assert default_entity.id == default and default_entity.idle_timeout_seconds == DEFAULT_SESSION_IDLE_SECONDS


async def test_reuse_follows_the_session_timeout_not_the_current_key_value(tracker, repo):
    """A Session keeps the timeout it opened with: shortening the key's value later does not end it early."""
    base = await _principal("j@test.local")
    opened_with_long = Principal(user_id=base.user_id, api_key_id=base.api_key_id, session_idle_seconds=3600)
    now_short = Principal(user_id=base.user_id, api_key_id=base.api_key_id, session_idle_seconds=60)

    first = await tracker.resolve(opened_with_long, CLIENT)
    await repo.update_activity(first, datetime.now(UTC) - timedelta(seconds=600))

    assert await tracker.resolve(now_short, CLIENT) == first

    await repo.update_activity(first, datetime.now(UTC) - timedelta(seconds=3605))
    replaced = await tracker.resolve(now_short, CLIENT)
    assert replaced != first
    assert (await repo.get_by_id(first, user_id=base.user_id)).status == SessionStatus.COMPLETED
    new_entity = await repo.find_active_by_fingerprint(base.user_id, client_fingerprint(base, CLIENT))
    assert new_entity.id == replaced and new_entity.idle_timeout_seconds == 60
