"""Correlation ID and request lifecycle logging middleware."""

import time
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import logger, set_correlation_id


class CorrelationAndLoggingMiddleware:
    """Pure ASGI middleware for correlation IDs and request timing without taskgroup conflicts."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Internally generate unique correlation ID in backend for every request
        corr_id = str(uuid.uuid4())
        set_correlation_id(corr_id)

        start_time = time.perf_counter()
        method = scope.get("method", "")
        path = scope.get("path", "")
        logger.info(f"Started {method} {path}")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                resp_headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-correlation-id"]
                resp_headers.append((b"x-correlation-id", corr_id.encode("latin1")))
                message["headers"] = resp_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Finished {method} {path} in {duration_ms:.2f}ms")
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Failed {method} {path} after {duration_ms:.2f}ms: {exc}",
                exc_info=True,
            )
            raise
