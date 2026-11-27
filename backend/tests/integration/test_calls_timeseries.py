"""GET /api/v1/executions/timeseries: calls counted per time bucket, from the execution history."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient

from tests.integration.test_tool_usage import record, user_id_of

URL = "/api/v1/executions/timeseries"


def totals(body: dict) -> list[int]:
    return [bucket["total_calls"] for bucket in body["buckets"]]


async def test_last_24_hours_in_hourly_buckets(async_client: AsyncClient):
    me, server = await user_id_of(async_client), uuid4()
    await record(me, "a", server_id=server, age=timedelta(minutes=10))
    await record(me, "a", server_id=server, status="failed", age=timedelta(minutes=20))
    await record(me, "a", server_id=server, status="rejected", age=timedelta(hours=5, minutes=30))
    await record(me, "a", server_id=server, age=timedelta(days=2))  # outside the range

    res = await async_client.get(URL, params={"range": "24h"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["range"] == "24h" and body["bucket_seconds"] == 3600
    assert len(body["buckets"]) == 24
    assert sum(totals(body)) == 3

    last, five_hours_ago = body["buckets"][-1], body["buckets"][18]
    assert (last["total_calls"], last["completed_calls"], last["failed_calls"]) == (2, 1, 1)
    assert (five_hours_ago["total_calls"], five_hours_ago["rejected_calls"]) == (1, 1)

    # Buckets are contiguous and start at `since`.
    starts = [datetime.fromisoformat(bucket["start"]) for bucket in body["buckets"]]
    assert starts[0] == datetime.fromisoformat(body["since"])
    assert all(later - earlier == timedelta(hours=1) for earlier, later in zip(starts, starts[1:], strict=False))


async def test_bucket_width_follows_the_range(async_client: AsyncClient):
    expected = {"1h": (300, 12), "7d": (21600, 28), "30d": (86400, 30)}
    for usage_range, (seconds, count) in expected.items():
        body = (await async_client.get(URL, params={"range": usage_range})).json()
        assert (body["bucket_seconds"], len(body["buckets"])) == (seconds, count), usage_range


async def test_all_time_starts_on_the_day_of_the_first_call(async_client: AsyncClient):
    empty = (await async_client.get(URL, params={"range": "all"})).json()
    assert empty["since"] is None and empty["buckets"] == []

    me, server = await user_id_of(async_client), uuid4()
    await record(me, "a", server_id=server, age=timedelta(days=3))
    await record(me, "a", server_id=server)

    body = (await async_client.get(URL, params={"range": "all"})).json()
    since = datetime.fromisoformat(body["since"])
    assert (since.hour, since.minute, since.second) == (0, 0, 0)
    assert since <= datetime.now(UTC) - timedelta(days=3)
    assert body["bucket_seconds"] == 86400
    assert 4 <= len(body["buckets"]) <= 5
    assert sum(totals(body)) == 2


async def test_server_filter(async_client: AsyncClient):
    me = await user_id_of(async_client)
    jira, github = uuid4(), uuid4()
    await record(me, "a", server_id=jira)
    await record(me, "a", server_id=github)
    await record(me, "a", server_id=github)

    body = (await async_client.get(URL, params={"range": "1h", "server_id": str(github)})).json()
    assert body["server_id"] == str(github)
    assert sum(totals(body)) == 2


async def test_only_the_callers_own_calls_are_counted(async_client: AsyncClient, other_user_client: AsyncClient):
    other = await user_id_of(other_user_client)
    await record(other, "theirs", server_id=uuid4())

    assert sum(totals((await async_client.get(URL, params={"range": "1h"})).json())) == 0


async def test_rejects_unknown_ranges_and_requires_login(async_client: AsyncClient, anon_client: AsyncClient):
    assert (await async_client.get(URL, params={"range": "1y"})).status_code == 422
    assert (await anon_client.get(URL)).status_code == 401
