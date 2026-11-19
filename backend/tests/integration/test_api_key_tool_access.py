"""Per-API-key tool visibility (ADR-0007): a tool hidden from a key is not searchable or runnable with that key."""

import sys
from pathlib import Path
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.api.dependencies import get_tool_catalog_service, get_tool_executor_service
from app.core.enums.execution_enum import ExecutionOutcomeKind, RejectionReason
from app.infrastructure.repositories.tool_access_repository import PostgresToolAccessRepository

DEMO_SERVER = str(Path(__file__).resolve().parent.parent.parent / "demo_server" / "server.py")


async def connected_demo_server(client: AsyncClient) -> str:
    server = (
        await client.post(
            "/api/v1/servers",
            json={"name": "math", "transport": "stdio", "stdio_config": {"command": sys.executable, "args": [DEMO_SERVER]}},
        )
    ).json()
    assert (await client.post(f"/api/v1/servers/{server['id']}/refresh-tools")).status_code == 200
    return server["id"]


async def new_key(client: AsyncClient, name: str) -> str:
    return (await client.post("/api/v1/auth/api-keys", json={"name": name})).json()["id"]


def tools_url(key_id: str, server_id: str, tool_name: str | None = None) -> str:
    url = f"/api/v1/auth/api-keys/{key_id}/servers/{server_id}/tools"
    return f"{url}/{tool_name}" if tool_name else url


async def searchable(user_id: UUID, key_id: str | None, query: str = "calculate a math expression") -> set[str]:
    [ranked] = await get_tool_catalog_service().search([query], user_id=user_id, top_k=10, api_key_id=UUID(key_id) if key_id else None)
    return {tool.name for tool, _ in ranked}


async def test_every_tool_is_visible_until_hidden_and_the_setting_round_trips(async_client):
    server_id = await connected_demo_server(async_client)
    key = await new_key(async_client, "ci")

    listed = (await async_client.get(tools_url(key, server_id))).json()
    assert {t["name"] for t in listed} == {"calculate", "echo", "system_ping"}
    assert all(t["enabled"] for t in listed)

    for _ in range(2):  # idempotent
        hidden = await async_client.patch(tools_url(key, server_id, "calculate"), json={"enabled": False})
        assert hidden.status_code == 200, hidden.text
        assert hidden.json() == {"tool_name": "calculate", "enabled": False}
    states = {t["name"]: t["enabled"] for t in (await async_client.get(tools_url(key, server_id))).json()}
    assert states == {"calculate": False, "echo": True, "system_ping": True}

    for _ in range(2):
        assert (await async_client.patch(tools_url(key, server_id, "calculate"), json={"enabled": True})).status_code == 200
    assert all(t["enabled"] for t in (await async_client.get(tools_url(key, server_id))).json())


async def test_hidden_tool_is_left_out_of_that_keys_search_only(async_client, user_id):
    server_id = await connected_demo_server(async_client)
    key_a, key_b = await new_key(async_client, "a"), await new_key(async_client, "b")
    await async_client.patch(tools_url(key_a, server_id, "calculate"), json={"enabled": False})

    assert "calculate" not in await searchable(user_id, key_a)
    assert "calculate" in await searchable(user_id, key_b)
    assert "calculate" in await searchable(user_id, None)  # the console is not limited by key

    # Re-discovery gives the tool a new id; the setting is by name, so it still applies
    assert (await async_client.post(f"/api/v1/servers/{server_id}/refresh-tools")).status_code == 200
    assert "calculate" not in await searchable(user_id, key_a)

    await async_client.patch(tools_url(key_a, server_id, "calculate"), json={"enabled": True})
    assert "calculate" in await searchable(user_id, key_a)


async def test_running_a_hidden_tool_with_that_key_is_a_rejected_execution(async_client, user_id):
    server_id = await connected_demo_server(async_client)
    key_a, key_b = await new_key(async_client, "a"), await new_key(async_client, "b")
    await async_client.patch(tools_url(key_a, server_id, "calculate"), json={"enabled": False})
    executor = get_tool_executor_service()

    def run(api_key_id):
        return executor.execute(
            "calculate",
            {"expression": "6*7"},
            user_id=user_id,
            server_id=UUID(server_id),
            api_key_id=UUID(api_key_id) if api_key_id else None,
        )

    rejected = await run(key_a)
    assert rejected.kind == ExecutionOutcomeKind.REJECTED
    assert rejected.rejection_reason == RejectionReason.TOOL_DISABLED
    assert "not enabled for this API key" in rejected.error_message
    recorded = (await async_client.get(f"/api/v1/executions/{rejected.execution_id}")).json()
    assert recorded["status"] == "rejected"

    assert (await run(key_b)).kind == ExecutionOutcomeKind.SUCCEEDED
    assert (await run(None)).kind == ExecutionOutcomeKind.SUCCEEDED


async def test_unknown_tool_revoked_key_and_extra_fields_are_refused(async_client):
    server_id = await connected_demo_server(async_client)
    key = await new_key(async_client, "k")

    assert (await async_client.patch(tools_url(key, server_id, "nope"), json={"enabled": False})).status_code == 404
    assert (await async_client.patch(tools_url(key, server_id, "calculate"), json={"enabled": False, "x": 1})).status_code == 422
    assert (await async_client.get(tools_url(str(uuid4()), server_id))).status_code == 404
    assert (await async_client.get(tools_url(key, str(uuid4())))).status_code == 404

    assert (await async_client.delete(f"/api/v1/auth/api-keys/{key}")).status_code == 204
    assert (await async_client.get(tools_url(key, server_id))).status_code == 404


async def test_deleting_the_server_removes_its_hidden_tool_rows(async_client):
    server_id = await connected_demo_server(async_client)
    key = await new_key(async_client, "k")
    await async_client.patch(tools_url(key, server_id, "echo"), json={"enabled": False})
    repository = PostgresToolAccessRepository()
    assert await repository.disabled_tool_names(UUID(key), UUID(server_id)) == {"echo"}

    assert (await async_client.delete(f"/api/v1/servers/{server_id}")).status_code in (200, 204)
    assert await repository.disabled_tool_names(UUID(key), UUID(server_id)) == set()
