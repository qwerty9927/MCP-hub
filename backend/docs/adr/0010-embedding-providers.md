# ADR 0010: Embedding Providers: Local fastembed or Cloudflare Workers AI

## Status
Accepted

## Date
2026-11-26

## Context
Tool search (ADR-0006) embedded Tools and queries with a fastembed model in the hub process. That costs about 64 MB of model and memory per process, plus CPU on every discovery and search. Some deployments would rather call a hosted model. Others want to keep everything local. Stored vectors live in `discovered_tools.embedding`, so a provider switch must not make them meaningless.

## Decision
1. **One model, two providers.** `EMBEDDING_MODEL` names the model independently of who runs it (`bge-small-en-v1.5`). `EMBEDDING_MODELS`, a JSON setting, maps it to its dimension, each provider's id (`BAAI/bge-small-en-v1.5` for fastembed, `@cf/baai/bge-small-en-v1.5` for Workers AI) and the Workers AI pooling that reproduces the local vectors (`EmbeddingModelSpec` in `app/schemas/embedding_schema.py`; `Settings.embedding_model_spec` returns the selected entry). No model name appears in the Python code. Settings validation rejects an unknown model or an `EMBEDDING_DIMENSION` that does not match it.
2. **`EMBEDDING_PROVIDER` picks the source**: `local` (fastembed, in-process) or `cloudflare` (Workers AI over HTTPS, using `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`, which must then be non-empty, at `CLOUDFLARE_API_BASE_URL` with `CLOUDFLARE_REQUEST_TIMEOUT_SECONDS` per request).
3. **Same vectors from both.** fastembed's bge-small-en-v1.5 uses the CLS token with no query prefix. Workers AI defaults to mean pooling, so the catalog entry sets `cloudflare_pooling: "cls"` and every request sends it. Both results are L2-normalized. Switching providers therefore needs no re-embedding. The opt-in test `test_cloudflare_and_local_embed_alike` (`RUN_CLOUDFLARE=1`) checks the cosine similarity of the two is above 0.99.
4. **Chosen once, at wiring time.** `create_embedding_service(settings)` in `app/infrastructure/embedding/embedding_factory.py` is the only code that reads `EMBEDDING_PROVIDER`. `app/api/dependencies.py` calls it once. Services see only `EmbeddingServiceAbstract`.
5. **The backfill can use the Batch API.** With `EMBEDDING_BACKFILL_QUEUED=true`, the backfill calls `embed_documents_queued` instead of `embed_documents`.
   - On Cloudflare that is one Batch API submission (`?queueRequest=true`, `{"requests": [{"text": [≤100], "pooling"}, …]}`) per backfill round, under 10 MB. It is polled every `CLOUDFLARE_BATCH_POLL_INTERVAL_SECONDS` until it is done, and given up after `CLOUDFLARE_BATCH_TIMEOUT_SECONDS`.
   - Replies recorded live on 2026-11-26: submit → HTTP 202 `{status: "queued", request_id}`. Each poll → `status` `queued`, then `running` (about 25 s for a small batch). When done → `responses[]` of `{id, success, result: {data, shape, pooling}}`, matched back by `id`. An unknown `request_id` → HTTP 404, code 5504.
   - Any failed item, or the timeout, fails the round. Its Tools stay unembedded and the next run resubmits them. An abandoned batch may still finish on Cloudflare, so the rare duplicate is paid for.
   - The local provider has no queue: its `embed_documents_queued` is `embed_documents`.
   - Discovery and search always embed directly, because they need the vectors now.
6. **Layering.**
   - `app/infrastructure/cloudflare/workers_ai_client.py` is a transport-only connector: URL, bearer token, and Cloudflare's `{success, errors, result}` envelope.
   - `app/infrastructure/embedding/` holds the port and its two adapters.
   - `tool_embedding_text`, which decides the text that represents a Tool, is business logic and stays in `app/services/tool_catalog.py`.

## Why
- **A provider-neutral model name over one id per provider:** the model, not the provider, decides whether stored vectors are valid. One field makes "same model" a guarantee rather than a convention.
- **Factory at startup over a per-call switch:** the choice never changes while the process runs, and a misconfiguration (missing token, wrong dimension) fails at startup through settings validation and `warm_up`, not on the first search.
- **Plain httpx over a Cloudflare SDK:** one endpoint, no new dependency, and `httpx.MockTransport` makes it testable offline.

## Consequences
- With `cloudflare`, tool metadata and search queries leave the hub for Cloudflare, and search depends on the network and Cloudflare's rate limits. When an API call fails, discovery stores Tools without embeddings and the backfill (ADR-0006) retries them; a failed query embedding makes that `SEARCH_TOOLS` call return an error.
- Requests carry at most 100 texts (`CLOUDFLARE_MAX_TEXTS_PER_REQUEST`), so a large Server's discovery makes several calls.
- A queued backfill is slower than direct calls (tens of seconds or more per round), but Cloudflare fulfils it eventually rather than erroring when short of capacity. With the queue, `EMBEDDING_BACKFILL_BATCH` can be raised well above 64, since one submission carries the whole round.
- `fastembed` stays a dependency and the Docker image still ships the local model, so `local` keeps working offline. With `cloudflare` the model is never loaded.
- Adding a model means adding an `EMBEDDING_MODELS` entry in `.env` (dimension, ids, pooling); no code change. The Docker image pre-downloads the local model named by the `EMBEDDING_LOCAL_MODEL_ID` build arg. A model of another dimension also needs a migration that resizes the column (ADR-0006).
