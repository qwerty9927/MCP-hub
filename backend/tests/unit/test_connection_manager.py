"""Unit tests for ConnectionManager locking and session reuse."""

import asyncio
from uuid import uuid4

import pytest

import app.services.connection_manager as cm_module
from app.core.enums.server_enum import TransportType
from app.domain.server_entity import ServerEntity
from app.services.connection_manager import ConnectionManager


class FakeSession:
    def __init__(self) -> None:
        self.pings = 0
        self.ping_error: Exception | None = None

    async def send_ping(self) -> None:
        self.pings += 1
        if self.ping_error:
            raise self.ping_error


class FakeWorker:
    """Stands in for SessionWorker; `gates` lets a test hold a Server's connect open."""

    gates: dict[str, asyncio.Event] = {}
    started: list[str] = []
    stopped: list[str] = []

    def __init__(self, server: ServerEntity, settings: object, semaphore: asyncio.Semaphore) -> None:
        self.server = server
        self.semaphore = semaphore
        self.session: FakeSession | None = None
        self.is_alive = False
        self.last_verified_at = 0.0

    async def start(self, timeout: float | None = None) -> FakeSession:
        FakeWorker.started.append(self.server.name)
        gate = FakeWorker.gates.get(self.server.name)
        if gate:
            await gate.wait()
        self.session = FakeSession()
        self.is_alive = True
        return self.session

    async def stop(self) -> None:
        FakeWorker.stopped.append(self.server.name)
        self.is_alive = False


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> ConnectionManager:
    FakeWorker.gates = {}
    FakeWorker.started = []
    FakeWorker.stopped = []
    monkeypatch.setattr(cm_module, "SessionWorker", FakeWorker)
    return ConnectionManager()


def make_server(name: str) -> ServerEntity:
    return ServerEntity(id=uuid4(), name=name, transport=TransportType.STDIO)


async def test_slow_connect_does_not_block_other_servers(manager: ConnectionManager):
    slow, fast = make_server("slow"), make_server("fast")
    FakeWorker.gates["slow"] = asyncio.Event()

    slow_task = asyncio.create_task(manager.get_or_create_session(slow))
    await asyncio.sleep(0)  # let the slow connect take its lock and block

    await asyncio.wait_for(manager.get_or_create_session(fast), timeout=1.0)
    assert not slow_task.done()

    FakeWorker.gates["slow"].set()
    await slow_task


async def test_concurrent_calls_for_one_server_create_one_worker(manager: ConnectionManager):
    server = make_server("solo")
    FakeWorker.gates["solo"] = asyncio.Event()

    first = asyncio.create_task(manager.get_or_create_session(server))
    second = asyncio.create_task(manager.get_or_create_session(server))
    await asyncio.sleep(0)
    FakeWorker.gates["solo"].set()

    assert await first is await second
    assert FakeWorker.started == ["solo"]


async def test_recently_verified_session_is_reused_without_ping(manager: ConnectionManager):
    server = make_server("fresh")
    session = await manager.get_or_create_session(server)

    assert await manager.get_or_create_session(server) is session
    assert session.pings == 0


async def test_stale_session_is_pinged_then_reused(manager: ConnectionManager):
    server = make_server("stale")
    session = await manager.get_or_create_session(server)
    manager._workers[server.id].last_verified_at -= cm_module.SESSION_PING_INTERVAL_SECONDS + 1

    assert await manager.get_or_create_session(server) is session
    assert session.pings == 1
    # The successful ping counts as a verification, so the next call skips it.
    await manager.get_or_create_session(server)
    assert session.pings == 1


async def test_failed_ping_reconnects(manager: ConnectionManager):
    server = make_server("flaky")
    session = await manager.get_or_create_session(server)
    session.ping_error = RuntimeError("connection closed")
    manager._workers[server.id].last_verified_at -= cm_module.SESSION_PING_INTERVAL_SECONDS + 1

    replacement = await manager.get_or_create_session(server)

    assert replacement is not session
    assert FakeWorker.stopped == ["flaky"]
    assert FakeWorker.started == ["flaky", "flaky"]


async def test_dead_worker_is_replaced(manager: ConnectionManager):
    server = make_server("dead")
    session = await manager.get_or_create_session(server)
    manager._workers[server.id].is_alive = False

    assert await manager.get_or_create_session(server) is not session
