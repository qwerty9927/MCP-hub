"""Main FastAPI application entry point for MCP Hub Backend."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Route

from app.api.dependencies import (
    get_auth_service,
    get_connection_manager,
    get_embedding_backfill_service,
    get_embedding_service,
    get_mcp_server,
    get_oauth_flow_registry,
    get_session_sweeper_service,
)
from app.api.v1.api_key_tools_router import router as api_key_tools_router
from app.api.v1.auth_router import router as auth_router
from app.api.v1.executions_router import router as executions_router
from app.api.v1.oauth_router import router as oauth_router
from app.api.v1.servers_router import router as servers_router
from app.api.v1.sessions_router import router as sessions_router
from app.api.v1.system_router import router as system_router
from app.api.v1.tools_router import router as tools_router
from app.background_service.scheduler import create_scheduler
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_correlation_id, logger, setup_logging
from app.middlewares.correlation import CorrelationAndLoggingMiddleware
from app.schemas.common_schema import ErrorDetail, ErrorResponse
from app.services.embedding_service import warm_up


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown hooks."""
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")

    # Tool search (ADR-0006): load the embedding model, then embed any Tools stored without an embedding.
    await warm_up(get_embedding_service())
    embedding_backfill = get_embedding_backfill_service()
    backfill = asyncio.create_task(embedding_backfill.backfill_embeddings())

    # Start MCP Server Streamable HTTP lifecycle
    mcp_server = get_mcp_server()
    async with mcp_server.run():
        # Background jobs (app/background_service/). A fresh scheduler per lifespan: one cannot restart after shutdown.
        scheduler = create_scheduler(get_session_sweeper_service(), embedding_backfill, get_auth_service().purge_expired_refresh_tokens)
        scheduler.start()
        logger.info(f"Background scheduler started with jobs: {[job.id for job in scheduler.get_jobs()]}")
        try:
            yield
        finally:
            scheduler.shutdown(wait=False)
            backfill.cancel()
            logger.info("Background scheduler shut down.")

    logger.info("Initiating graceful shutdown...")
    await get_oauth_flow_registry().shutdown()
    connection_manager = get_connection_manager()
    await connection_manager.shutdown()
    logger.info("Graceful shutdown complete.")


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

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "x-correlation-id"],
    )

    # Pure ASGI middleware for correlation IDs (outermost layer to trace all incoming requests)
    app.add_middleware(CorrelationAndLoggingMiddleware)

    # Custom Exception Handlers
    @app.exception_handler(AppError)
    async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
        correlation_id = get_correlation_id()
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=str(exc.status_code),
                message=exc.message,
                details=exc.details,
                correlation_id=correlation_id,
            )
        )
        headers = {"X-Correlation-ID": correlation_id}
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        correlation_id = get_correlation_id()
        errors = [
            {
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors()
        ]
        error_response = ErrorResponse(
            error=ErrorDetail(
                code="ValidationError",
                message="Request validation failed",
                details=errors,
                correlation_id=correlation_id,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": correlation_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        correlation_id = get_correlation_id()
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                correlation_id=correlation_id,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": correlation_id},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = get_correlation_id()
        logger.error(f"Unhandled server error: {exc}", exc_info=True)
        error_response = ErrorResponse(
            error=ErrorDetail(
                code="InternalServerError",
                message="An unexpected internal error occurred. Please try again later.",
                details={"correlation_id": correlation_id},
                correlation_id=correlation_id,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
            headers={"X-Correlation-ID": correlation_id},
        )

    # Mount System probes at Root (/health, /ready, /metrics)
    app.include_router(system_router)

    # Mount API v1 routes
    from fastapi import APIRouter

    v1_router = APIRouter(prefix=settings.API_V1_STR)
    v1_router.include_router(auth_router)
    v1_router.include_router(api_key_tools_router)
    v1_router.include_router(servers_router)
    v1_router.include_router(oauth_router)
    v1_router.include_router(tools_router)
    v1_router.include_router(executions_router)
    v1_router.include_router(sessions_router)
    v1_router.include_router(system_router, prefix="/system")

    app.include_router(v1_router)

    # Mount unified Streamable HTTP MCP Server endpoint at /mcp
    mcp_server = get_mcp_server()
    app.routes.append(
        Route(
            "/mcp",
            endpoint=mcp_server.get_proxy_asgi_app(),
            name="mcp_server",
            include_in_schema=False,
        )
    )

    return app


app = create_app()
