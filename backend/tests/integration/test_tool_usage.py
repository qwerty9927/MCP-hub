"""GET /api/v1/executions/tool-usage: the most-called tools over a period, from the execution history."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient

from app.domain.execution_entity import ExecutionEntity
from app.infrastructure.repositories.execution_repository import PostgresExecutionRepository

URL = "/api/v1/executions/tool-usage"


async def user_id_of(client: AsyncClient) -> UUID:
    return UUID((await client.get("/api/v1/auth/me")).json()["id"])


async def record(
    user_id: UUID,
    tool_name: str,
    *,
    server_id: UUID,
    server_name: str = "srv",
    status: str = "completed",
    duration_ms: float = 10.0,
    age: timedelta = timedelta(minutes=5),
) -> ExecutionEntity:
    return await PostgresExecutionRepository().create(
        ExecutionEntity(
            id=uuid4(),
            server_id=server_id,
            user_id=user_id,
            server_name=server_name,
            tool_name=tool_name,
            arguments={},
            is_error=status != "completed",
            duration_ms=duration_ms,
            executed_at=datetime.now(UTC) - age,
            status=status,
        )
    )


async def test_ranks_tools_by_calls_with_their_outcomes(async_client: AsyncClient):
    me, server = await user_id_of(async_client), uuid4()
    for _ in range(3):
        await record(me, "search", server_id=server, duration_ms=30.0)
    await record(me, "search", server_id=server, status="failed", duration_ms=60.0)
    await record(me, "search", server_id=server, status="rejected", duration_ms=0.0)
    await record(me, "echo", server_id=server)

    res = await async_client.get(URL)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["range"] == "7d" and body["since"] is not None
    assert body["total_calls"] == 6
    assert [item["tool_name"] for item in body["items"]] == ["search", "echo"]

    search = body["items"][0]
    assert (search["total_calls"], search["completed_calls"], search["failed_calls"], search["rejected_calls"]) == (5, 3, 1, 1)
    # Rejected calls never reached the server, so they do not pull the average down.
    assert search["avg_duration_ms"] == 37.5
    assert search["server_id"] == str(server) and search["server_name"] == "srv"


async def test_range_limits_the_period(async_client: AsyncClient):
    me, server = await user_id_of(async_client), uuid4()
    await record(me, "recent", server_id=server)
    await record(me, "three-days-old", server_id=server, age=timedelta(days=3))
    await record(me, "two-months-old", server_id=server, age=timedelta(days=60))

    def names(res) -> set[str]:
        assert res.status_code == 200, res.text
        return {item["tool_name"] for item in res.json()["items"]}

    assert names(await async_client.get(URL, params={"range": "24h"})) == {"recent"}
    assert names(await async_client.get(URL, params={"range": "7d"})) == {"recent", "three-days-old"}
    assert names(await async_client.get(URL, params={"range": "30d"})) == {"recent", "three-days-old"}
    all_time = await async_client.get(URL, params={"range": "all"})
    assert names(all_time) == {"recent", "three-days-old", "two-months-old"}
    assert all_time.json()["since"] is None


async def test_total_counts_every_call_not_only_the_listed_tools(async_client: AsyncClient):
    me, server = await user_id_of(async_client), uuid4()
    for tool, calls in (("a", 3), ("b", 2), ("c", 1)):
        for _ in range(calls):
            await record(me, tool, server_id=server)

    body = (await async_client.get(URL, params={"limit": 2})).json()
    assert [item["tool_name"] for item in body["items"]] == ["a", "b"]
    assert body["total_calls"] == 6


async def test_same_tool_name_on_two_servers_is_counted_apart(async_client: AsyncClient):
    me = await user_id_of(async_client)
    jira, github = uuid4(), uuid4()
    await record(me, "search", server_id=jira, server_name="jira")
    await record(me, "search", server_id=jira, server_name="jira")
    await record(me, "search", server_id=github, server_name="github")

    items = (await async_client.get(URL)).json()["items"]
    assert [(item["server_name"], item["total_calls"]) for item in items] == [("jira", 2), ("github", 1)]


async def test_only_the_callers_own_calls_are_counted(async_client: AsyncClient, other_user_client: AsyncClient):
    other = await user_id_of(other_user_client)
    await record(other, "theirs", server_id=uuid4())

    body = (await async_client.get(URL)).json()
    assert body["total_calls"] == 0 and body["items"] == []


async def test_rejects_unknown_ranges_and_limits(async_client: AsyncClient):
    assert (await async_client.get(URL, params={"range": "1y"})).status_code == 422
    assert (await async_client.get(URL, params={"limit": 0})).status_code == 422
    assert (await async_client.get(URL, params={"limit": 51})).status_code == 422


async def test_requires_login(anon_client: AsyncClient):
    assert (await anon_client.get(URL)).status_code == 401


async def test_execution_details_still_resolve_by_id(async_client: AsyncClient):
    """/tool-usage is declared before /{execution_id}; ids must still reach the details route."""
    execution = await record(await user_id_of(async_client), "echo", server_id=uuid4())
    res = await async_client.get(f"/api/v1/executions/{execution.id}")
    assert res.status_code == 200 and res.json()["tool_name"] == "echo"
