"""HTTP connector to Cloudflare Workers AI: runs one model on one input (ADR-0010).

It knows the transport (URL, bearer token, Cloudflare's response envelope), not what a model computes; the
embedding adapter in app/infrastructure/embedding/ builds the payload and reads the result.
"""

from typing import Any

import httpx


class CloudflareAPIError(Exception):
    """Workers AI refused or failed a request. The message carries Cloudflare's errors, never the API token."""

    def __init__(self, model_id: str, status_code: int, errors: list[str]) -> None:
        self.model_id = model_id
        self.status_code = status_code
        self.errors = errors
        detail = "; ".join(errors) if errors else "no error details"
        super().__init__(f"Cloudflare Workers AI request for '{model_id}' failed with HTTP {status_code}: {detail}")


class CloudflareWorkersAIClient:
    """POST /accounts/{account_id}/ai/run/{model_id} with a bearer token, returning the envelope's `result`."""

    def __init__(
        self,
        account_id: str,
        api_token: str,
        *,
        base_url: str,
        timeout_seconds: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """`base_url` and `timeout_seconds` come from CLOUDFLARE_API_BASE_URL / CLOUDFLARE_REQUEST_TIMEOUT_SECONDS."""
        self._account_id = account_id
        self._http = http_client or httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._headers = {"Authorization": f"Bearer {api_token}"}

    async def run(self, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run `model_id` on `payload`; raises CloudflareAPIError unless Cloudflare reports success."""
        return await self._post(model_id, payload)

    async def submit_batch(self, model_id: str, requests: list[dict[str, Any]]) -> str:
        """Queue `requests` (each one input of `model_id`) with the async Batch API; returns the batch's request_id.

        Queued work is "fulfilled eventually, rather than erroring out" when Cloudflare is short of capacity.
        """
        result = await self._post(model_id, {"requests": requests}, queued=True)
        request_id = result.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise CloudflareAPIError(model_id, 200, ["batch submission returned no request_id"])
        return request_id

    async def poll_batch(self, model_id: str, request_id: str) -> list[dict[str, Any]] | None:
        """The batch's per-request `responses` once it is done, else None while it is `queued` or `running`.

        Each response carries `id` (the index of its request), `success` and `result`. A finished batch can be
        polled again; an unknown request_id raises CloudflareAPIError (HTTP 404).
        """
        result = await self._post(model_id, {"request_id": request_id}, queued=True)
        responses = result.get("responses")
        if responses is None:
            return None
        if not isinstance(responses, list):
            raise CloudflareAPIError(model_id, 200, ["batch result has no responses list"])
        return responses

    async def _post(self, model_id: str, payload: dict[str, Any], *, queued: bool = False) -> dict[str, Any]:
        params = {"queueRequest": "true"} if queued else None
        response = await self._http.post(
            f"/accounts/{self._account_id}/ai/run/{model_id}", params=params, json=payload, headers=self._headers
        )
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise CloudflareAPIError(model_id, response.status_code, [f"unexpected response: {response.text[:200]}"])
        if response.is_error or not body.get("success", False):
            raise CloudflareAPIError(model_id, response.status_code, _error_messages(body))
        result = body.get("result")
        if not isinstance(result, dict):
            raise CloudflareAPIError(model_id, response.status_code, ["response has no result"])
        return result

    async def aclose(self) -> None:
        await self._http.aclose()


def _error_messages(body: dict[str, Any]) -> list[str]:
    messages = []
    for error in body.get("errors") or []:
        if isinstance(error, dict):
            code = error.get("code")
            message = str(error.get("message", ""))
            messages.append(f"{code}: {message}" if code is not None else message)
        else:
            messages.append(str(error))
    return messages
