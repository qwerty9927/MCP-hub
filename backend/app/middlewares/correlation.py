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
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        start_time = time.perf_counter()
        method = scope.get("method", "")
        path = scope.get("path", "")
        logger.info(f"Started {method} {path}")

        status_code: int | None = None

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-correlation-id"]
                response_headers.append((b"x-correlation-id", correlation_id.encode("latin1")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Finished {method} {path} {status_code} in {duration_ms:.2f}ms")
        except Exception as exc:
            # The 500 response and its traceback come from the app's generic exception handler (app/main.py),
            # which Starlette runs outside this middleware: log the outcome once here, without a second traceback.
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Failed {method} {path} 500 after {duration_ms:.2f}ms: {type(exc).__name__}: {exc}")
            raise
