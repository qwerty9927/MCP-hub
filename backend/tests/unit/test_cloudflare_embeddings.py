"""EMBEDDING_PROVIDER=cloudflare (ADR-0010): the Workers AI connector, the embedding adapter, the factory, settings.

The HTTP API is replaced by httpx.MockTransport, so nothing leaves the machine.
"""

import json

import httpx
import numpy as np
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.infrastructure.cloudflare.workers_ai_client import CloudflareAPIError, CloudflareWorkersAIClient
from app.infrastructure.embedding.cloudflare_embedding_service import CloudflareEmbeddingService
from app.infrastructure.embedding.embedding_factory import create_embedding_service
from app.infrastructure.embedding.fastembed_service import FastEmbedService

ACCOUNT = "acct-123"
TOKEN = "secret-token-value"
MODEL = "@cf/baai/bge-small-en-v1.5"
BASE_URL = "https://api.cloudflare.test/client/v4"


def vector(seed: int, dimension: int = 384) -> list[float]:
    return np.random.default_rng(seed).standard_normal(dimension).tolist()


def embedding_api(requests: list[httpx.Request], *, dimension: int = 384, rows: int | None = None):
    """A Workers AI stand-in that records requests and returns one (unnormalized) vector per text."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        texts = json.loads(request.content)["text"]
        count = len(texts) if rows is None else rows
        data = [vector(len(requests) * 1000 + i, dimension) for i in range(count)]
        return httpx.Response(200, json={"result": {"shape": [count, dimension], "data": data}, "success": True, "errors": []})

    return handler


def client_for(handler) -> CloudflareWorkersAIClient:
    http = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return CloudflareWorkersAIClient(account_id=ACCOUNT, api_token=TOKEN, base_url=BASE_URL, timeout_seconds=5, http_client=http)


def adapter_for(client: CloudflareWorkersAIClient, *, timeout: float = 5.0) -> CloudflareEmbeddingService:
    return CloudflareEmbeddingService(client, MODEL, 384, "cls", batch_poll_interval_seconds=0.001, batch_timeout_seconds=timeout)


class BatchAPI:
    """A stateful Batch API stand-in, shaped like the live replies recorded on 2026-11-26.

    Submit (?queueRequest=true, {"requests": [...]}) -> 202 {status: queued, request_id}. Each poll
    ({"request_id"}) answers `queued`, then `running`, then the finished `responses` (in `order`, to show they are
    matched back by id). `fail` makes that request index unsuccessful; `never_done` keeps it running forever.
    """

    def __init__(self, *, polls_before_done: int = 2, order=None, fail: int | None = None, never_done: bool = False) -> None:
        self.submitted: list[dict] = []
        self.polls = 0
        self.sync_calls = 0
        self._polls_before_done = polls_before_done
        self._order = order
        self._fail = fail
        self._never_done = never_done

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.params.get("queueRequest") != "true":
            self.sync_calls += 1
            return httpx.Response(500, json={"success": False, "errors": [{"code": 1, "message": "sync call not expected"}]})
        if "requests" in body:
            self.submitted.append(body)
            return httpx.Response(202, json={"result": {"status": "queued", "request_id": "req-1", "model": MODEL}, "success": True})
        if body.get("request_id") != "req-1":
            error = {"code": 5504, "message": f"AiError: AiError: Request not found in queue ({body.get('request_id')})"}
            return httpx.Response(404, json={"result": {}, "success": False, "errors": [error]})
        self.polls += 1
        if self._never_done or self.polls <= self._polls_before_done:
            status = "queued" if self.polls == 1 else "running"
            return httpx.Response(200, json={"result": {"status": status, "request_id": "req-1", "model": MODEL}, "success": True})
        items = self.submitted[-1]["requests"]
        responses = [
            {
                "id": index,
                "success": index != self._fail,
                "result": {"data": [vector(index * 1000 + i) for i in range(len(item["text"]))], "pooling": "cls"},
            }
            for index, item in enumerate(items)
        ]
        if self._order:
            responses = [responses[i] for i in self._order]
        return httpx.Response(200, json={"result": {"responses": responses, "usage": {"prompt_tokens": 1}}, "success": True})


async def test_client_posts_to_the_model_with_the_bearer_token_and_returns_the_result():
    requests: list[httpx.Request] = []
    client = client_for(embedding_api(requests))

    result = await client.run(MODEL, {"text": ["a", "b"], "pooling": "cls"})

    [request] = requests
    assert request.method == "POST"
    assert str(request.url) == f"{BASE_URL}/accounts/{ACCOUNT}/ai/run/{MODEL}"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(request.content) == {"text": ["a", "b"], "pooling": "cls"}
    assert result["shape"] == [2, 384]


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (401, {"success": False, "errors": [{"code": 10000, "message": "Authentication error"}], "result": None}),
        (429, {"success": False, "errors": [{"code": 3036, "message": "Rate limited"}], "result": None}),
        (200, {"success": False, "errors": [{"code": 5006, "message": "Bad input"}], "result": None}),
    ],
)
async def test_client_raises_cloudflares_error_without_the_token(status, body):
    client = client_for(lambda request: httpx.Response(status, json=body))

    with pytest.raises(CloudflareAPIError) as raised:
        await client.run(MODEL, {"text": ["a"]})

    assert raised.value.status_code == status
    assert body["errors"][0]["message"] in str(raised.value)
    assert TOKEN not in str(raised.value)


async def test_client_raises_on_a_non_json_response():
    client = client_for(lambda request: httpx.Response(502, text="<html>Bad gateway</html>"))

    with pytest.raises(CloudflareAPIError, match="HTTP 502"):
        await client.run(MODEL, {"text": ["a"]})


async def test_documents_are_sent_in_chunks_of_100_and_come_back_in_order_as_unit_vectors():
    requests: list[httpx.Request] = []
    service = adapter_for(client_for(embedding_api(requests)))

    vectors = await service.embed_documents([f"text {i}" for i in range(150)])

    assert [len(json.loads(r.content)["text"]) for r in requests] == [100, 50]
    assert json.loads(requests[1].content)["text"][0] == "text 100"
    assert all(json.loads(r.content)["pooling"] == "cls" for r in requests)
    assert len(vectors) == 150
    assert all(abs(float(np.linalg.norm(v)) - 1.0) < 1e-5 for v in vectors)
    # order kept: the first vector of the second request is the 101st result
    expected = np.asarray(vector(2000))
    assert np.allclose(vectors[100], expected / np.linalg.norm(expected), atol=1e-6)


async def test_query_is_one_request_with_one_text():
    requests: list[httpx.Request] = []
    service = adapter_for(client_for(embedding_api(requests)))

    query = await service.embed_query("send slack message")

    assert json.loads(requests[0].content) == {"text": ["send slack message"], "pooling": "cls"}
    assert len(query) == 384


async def test_no_documents_means_no_request():
    requests: list[httpx.Request] = []
    service = adapter_for(client_for(embedding_api(requests)))

    assert await service.embed_documents([]) == []
    assert requests == []


async def test_wrong_dimension_or_row_count_is_an_error():
    wrong_size = adapter_for(client_for(embedding_api([], dimension=768)))
    with pytest.raises(ValueError, match="768 dimensions"):
        await wrong_size.embed_query("x")

    missing_row = adapter_for(client_for(embedding_api([], rows=1)))
    with pytest.raises(ValueError, match="1 vectors for 2 texts"):
        await missing_row.embed_documents(["a", "b"])


async def test_factory_builds_the_provider_the_setting_names():
    settings = get_settings()

    local = create_embedding_service(settings.model_copy(update={"EMBEDDING_PROVIDER": "local"}))
    cloudflare = create_embedding_service(
        settings.model_copy(update={"EMBEDDING_PROVIDER": "cloudflare", "CLOUDFLARE_ACCOUNT_ID": ACCOUNT, "CLOUDFLARE_API_TOKEN": TOKEN})
    )

    spec = settings.embedding_model_spec  # the EMBEDDING_MODELS entry EMBEDDING_MODEL names
    assert isinstance(local, FastEmbedService)
    assert local.model_name == spec.local_id
    assert isinstance(cloudflare, CloudflareEmbeddingService)
    assert cloudflare.model_id == spec.cloudflare_id
    http = cloudflare._client._http  # built from CLOUDFLARE_API_BASE_URL / CLOUDFLARE_REQUEST_TIMEOUT_SECONDS
    assert str(http.base_url).rstrip("/") == settings.CLOUDFLARE_API_BASE_URL
    assert http.timeout.read == settings.CLOUDFLARE_REQUEST_TIMEOUT_SECONDS
    assert cloudflare._poll_interval == settings.CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS
    assert cloudflare._batch_timeout == settings.CLOUDFLARE_BATCH_TIMEOUT_SECONDS
    assert local.dimension == cloudflare.dimension == spec.dimension == settings.EMBEDDING_DIMENSION
    await cloudflare.aclose()


def test_the_model_catalog_and_job_schedule_come_from_json_in_the_environment(monkeypatch):
    catalog = {
        "tiny": {"dimension": 8, "local_id": "org/tiny-local", "cloudflare_id": "@cf/org/tiny", "cloudflare_pooling": "mean"},
    }
    monkeypatch.setenv("EMBEDDING_MODELS", json.dumps(catalog))
    monkeypatch.setenv("EMBEDDING_MODEL", "tiny")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "8")
    monkeypatch.setenv("SESSION_SWEEP_CRON", '{"minute": "*/5"}')
    settings = Settings()

    assert settings.SESSION_SWEEP_CRON == {"minute": "*/5"}

    spec = settings.embedding_model_spec
    assert (spec.dimension, spec.local_id, spec.cloudflare_id, spec.cloudflare_pooling) == (8, "org/tiny-local", "@cf/org/tiny", "mean")


def test_settings_require_cloudflare_credentials_only_for_the_cloudflare_provider():
    with pytest.raises(ValidationError, match="CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN"):
        Settings(EMBEDDING_PROVIDER="cloudflare", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN=" ")

    assert Settings(EMBEDDING_PROVIDER="local", CLOUDFLARE_ACCOUNT_ID="", CLOUDFLARE_API_TOKEN="").EMBEDDING_PROVIDER == "local"
    assert Settings(EMBEDDING_PROVIDER="cloudflare", CLOUDFLARE_ACCOUNT_ID=ACCOUNT, CLOUDFLARE_API_TOKEN=TOKEN)


def test_settings_reject_an_unknown_model_or_a_mismatched_dimension():
    with pytest.raises(ValidationError, match="EMBEDDING_MODEL must be one of"):
        Settings(EMBEDDING_MODEL="not-in-the-catalog")
    with pytest.raises(ValidationError, match="EMBEDDING_DIMENSION is 768"):
        Settings(EMBEDDING_DIMENSION=768)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"SESSION_SWEEP_CRON": {"minutes": "*"}}, "SESSION_SWEEP_CRON needs CronTrigger fields only"),
        ({"EMBEDDING_BACKFILL_INTERVAL_MINUTES": 0}, "EMBEDDING_BACKFILL_INTERVAL_MINUTES must be positive"),
        ({"EMBEDDING_BACKFILL_BATCH": -1}, "EMBEDDING_BACKFILL_BATCH must be positive"),
        ({"SESSION_SWEEP_JOB_ID": "same", "REFRESH_TOKEN_PURGE_JOB_ID": "same"}, "must be distinct and non-empty"),
        ({"HNSW_ITERATIVE_SCAN": "relaxed_order"}, "HNSW_ITERATIVE_SCAN"),
        ({"CLOUDFLARE_API_BASE_URL": "http://api.cloudflare.com/client/v4"}, "must be an https:// URL"),
        ({"CLOUDFLARE_REQUEST_TIMEOUT_SECONDS": 0}, "CLOUDFLARE_REQUEST_TIMEOUT_SECONDS must be positive"),
        ({"CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS": -1}, "CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS must be positive"),
        ({"CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS": 60, "CLOUDFLARE_BATCH_TIMEOUT_SECONDS": 30}, "must be shorter than"),
    ],
)
def test_settings_reject_bad_job_and_search_settings(overrides, message):
    with pytest.raises(ValidationError, match=message):
        Settings(**overrides)


async def test_queued_embedding_submits_one_batch_polls_until_done_and_keeps_order():
    api = BatchAPI(polls_before_done=2, order=[1, 0])  # responses come back out of order
    service = adapter_for(client_for(api))

    vectors = await service.embed_documents_queued([f"text {i}" for i in range(150)])

    [submission] = api.submitted
    assert [len(item["text"]) for item in submission["requests"]] == [100, 50]
    assert all(item["pooling"] == "cls" for item in submission["requests"])
    assert api.polls == 3 and api.sync_calls == 0
    assert len(vectors) == 150
    first_of_second_chunk = np.asarray(vector(1000))
    assert np.allclose(vectors[100], first_of_second_chunk / np.linalg.norm(first_of_second_chunk), atol=1e-6)
    assert all(abs(float(np.linalg.norm(v)) - 1.0) < 1e-5 for v in vectors)


async def test_queued_embedding_of_nothing_sends_nothing():
    api = BatchAPI()
    assert await adapter_for(client_for(api)).embed_documents_queued([]) == []
    assert api.submitted == [] and api.polls == 0


async def test_a_failed_batch_item_fails_the_whole_call():
    service = adapter_for(client_for(BatchAPI(polls_before_done=0, fail=1)))

    with pytest.raises(ValueError, match="no successful result for request 1"):
        await service.embed_documents_queued([f"text {i}" for i in range(150)])


async def test_a_batch_not_done_in_time_raises_timeout():
    service = adapter_for(client_for(BatchAPI(never_done=True)), timeout=0.02)

    with pytest.raises(TimeoutError, match="req-1"):
        await service.embed_documents_queued(["a"])


async def test_polling_an_unknown_batch_raises_cloudflares_error():
    client = client_for(BatchAPI())

    with pytest.raises(CloudflareAPIError, match="5504: AiError: AiError: Request not found in queue"):
        await client.poll_batch(MODEL, "no-such-request")


async def test_an_oversized_batch_is_refused_before_it_is_sent():
    api = BatchAPI()
    service = adapter_for(client_for(api))

    with pytest.raises(ValueError, match="the Batch API takes under"):
        await service.embed_documents_queued(["x" * 200_000] * 60)  # ~12 MB of JSON
    assert api.submitted == []


async def test_backfill_uses_the_queue_only_when_told_to():
    from app.background_service.embedding_backfill import EmbeddingBackfillService
    from tests.unit.test_embedding_backfill import InMemoryTools

    api = BatchAPI(polls_before_done=1)
    service = adapter_for(client_for(api))
    tools = InMemoryTools(3)

    assert await EmbeddingBackfillService(tools, service, 64, queued=True).backfill_embeddings() == 3
    assert len(api.submitted) == 1 and api.sync_calls == 0

    direct = BatchAPI()
    assert await EmbeddingBackfillService(InMemoryTools(2), adapter_for(client_for(direct)), 64).backfill_embeddings() == 0
    assert direct.sync_calls == 1 and direct.submitted == []  # direct path called the sync endpoint (refused here)


async def test_providers_without_a_queue_embed_directly_when_queued():
    from tests.fake_embeddings import FakeEmbeddingService

    fake = FakeEmbeddingService()
    assert await fake.embed_documents_queued(["send slack message"]) == await fake.embed_documents(["send slack message"])
