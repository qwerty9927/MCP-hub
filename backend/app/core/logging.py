"""Structured logging configuration and context management."""

import logging
import sys
import uuid
from contextvars import ContextVar

from app.core.config import get_settings

# ContextVar for request correlation ID
_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Retrieve current correlation ID or generate a default one."""
    cid = _correlation_id_ctx.get()
    if not cid:
        cid = str(uuid.uuid4())
        _correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    _correlation_id_ctx.set(correlation_id)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects the correlation_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id_ctx.get() or "-"
        return True


def setup_logging() -> None:
    """Initialize structured application logging."""
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = (
        "[%(asctime)s] [%(levelname)s] [corr_id:%(correlation_id)s] "
        "[%(name)s:%(funcName)s:%(lineno)d]: %(message)s"
    )

    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Avoid duplicate handlers if setup_logging is called multiple times
    root_logger.handlers = [handler]

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


logger = logging.getLogger("mcp_hub")
