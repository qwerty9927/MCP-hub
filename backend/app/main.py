"""Main FastAPI application entry point for MCP Hub Backend."""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.routing import Route

from app.api.dependencies import get_connection_manager, get_mcp_gateway, get_tool_catalog
from app.api.v1.executions import router as executions_router
from app.api.v1.servers import router as servers_router
from app.api.v1.system import router as system_router
from app.api.v1.tools import router as tools_router
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import get_correlation_id, logger, set_correlation_id, setup_logging
from app.infrastructure.database import init_db
from app.schemas.common import ErrorDetail, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown hooks."""
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")

    # Initialize SQLite database schema
    await init_db()

    # Preload discovered tools into catalog cache
    tool_catalog = get_tool_catalog()
    await tool_catalog.initialize_cache()

    # Start MCP Gateway Streamable HTTP lifecycle
    mcp_gateway = get_mcp_gateway()
    async with mcp_gateway.run():
        yield

    logger.info("Initiating graceful shutdown...")
    connection_manager = get_connection_manager()
    await connection_manager.shutdown()
    logger.info("Graceful shutdown complete.")


class CorrelationAndLoggingMiddleware:
    """Pure ASGI middleware for correlation IDs and request timing without taskgroup conflicts."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        corr_id = headers.get(b"x-correlation-id", b"").decode("latin1")
        if not corr_id:
            corr_id = str(uuid.uuid4())
        set_correlation_id(corr_id)

        start_time = time.perf_counter()
        method = scope.get("method", "")
        path = scope.get("path", "")
        logger.info(f"Started {method} {path}")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
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


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Production-oriented MCP Hub Backend that centrally manages multiple "
            "Model Context Protocol (MCP) servers and exposes their tools through a unified REST API."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Pure ASGI middleware for correlation IDs
    app.add_middleware(CorrelationAndLoggingMiddleware)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Exception Handlers
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=exc.__class__.__name__,
                message=exc.message,
                details=exc.details,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": get_correlation_id()},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "loc": list(err.get("loc", [])),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        error_response = ErrorResponse(
            error=ErrorDetail(
                code="ValidationError",
                message="Request validation failed",
                details=errors,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": get_correlation_id()},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled server error: {exc}", exc_info=True)
        error_response = ErrorResponse(
            error=ErrorDetail(
                code="InternalServerError",
                message="An unexpected internal error occurred. Please try again later.",
                details={"correlation_id": get_correlation_id()},
            )
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": get_correlation_id()},
        )

    # Mount System probes at Root (/health, /ready, /metrics)
    app.include_router(system_router)

    # Mount API v1 routes
    from fastapi import APIRouter

    v1_router = APIRouter(prefix=settings.API_V1_STR)
    v1_router.include_router(servers_router)
    v1_router.include_router(tools_router)
    v1_router.include_router(executions_router)
    v1_router.include_router(system_router, prefix="/system")

    app.include_router(v1_router)

    # Mount unified Streamable HTTP MCP Gateway endpoint at /mcp
    mcp_gateway = get_mcp_gateway()
    app.routes.append(
        Route(
            "/mcp",
            endpoint=mcp_gateway.get_proxy_asgi_app(),
            name="mcp_gateway",
            include_in_schema=False,
        )
    )

    return app


app = create_app()
