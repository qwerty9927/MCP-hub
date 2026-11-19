"""MCP Connection Manager for orchestrating client sessions and transport lifecycles."""

import asyncio
import time
from contextlib import AsyncExitStack
from typing import Any
from uuid import UUID

import httpx2
import mcp.types as mcp_types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from app.core.config import Settings, get_settings
from app.core.constants.oauth_constants import OAUTH_REAUTHORIZATION_REASON
from app.core.enums.server_enum import ServerAuthType, TransportType
from app.core.exceptions import (
    BadGatewayError,
    BadRequestError,
    GatewayTimeoutError,
    InternalServerError,
)
from app.core.logging import logger
from app.domain.server_entity import ServerEntity
from app.helpers.errors import find_oauth_error, format_mcp_error
from app.helpers.security import sanitize_environment, validate_http_url_resolved, validate_stdio_command
from app.infrastructure.oauth.client_provider import (
    DbTokenStorage,
    HubOAuthClientProvider,
    build_client_metadata,
)
from app.infrastructure.repositories.oauth_credential_repository import OAuthCredentialRepositoryAbstract

# A session verified (connected or pinged) this recently is reused without another ping.
SESSION_PING_INTERVAL_SECONDS = 10.0


class SessionWorker:
    """Manages an MCP client session inside a dedicated asyncio task.

    This ensures anyio cancel scopes and async context managers are entered
    and exited strictly in the same task, avoiding task-switch cancel scope errors.
    """

    def __init__(
        self,
        server: ServerEntity,
        settings: Settings,
        semaphore: asyncio.Semaphore,
        oauth_credentials: OAuthCredentialRepositoryAbstract | None = None,
        auth: httpx2.Auth | None = None,
    ) -> None:
        self.server = server
        self.settings = settings
        self.semaphore = semaphore
        self.oauth_credentials = oauth_credentials
        # Set only for a sign-in (ConnectionManager.authorize): its credentials live in memory until it succeeds.
        self.auth = auth
        self.session: ClientSession | None = None
        self.ready_event = asyncio.Event()
        self.stop_event = asyncio.Event()
        self.error: Exception | None = None
        self.task: asyncio.Task | None = None
        self.is_alive: bool = False
        self.last_verified_at: float = 0.0  # time.monotonic() of the last successful connect or ping

    async def start(self, timeout: float | None = None) -> ClientSession:
        """Launch the worker task and wait until session initialization completes."""
        connect_timeout = timeout or self.settings.DEFAULT_CONNECTION_TIMEOUT
        self.task = asyncio.create_task(self._run(timeout=connect_timeout))

        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=connect_timeout + 2.0)
        except TimeoutError as exc:
            await self.stop()
            raise BadGatewayError(
                f"Failed to connect to server '{self.server.id}': Connection timed out after {connect_timeout}s",
                details={
                    "server_id": str(self.server.id),
                    "reason": f"Connection timed out after {connect_timeout}s",
                },
            ) from exc

        if self.error:
            await self.stop()
            oauth_error = find_oauth_error(self.error) if self.server.auth_type == ServerAuthType.OAUTH else None
            if oauth_error is not None:
                raise BadGatewayError(
                    f"Server '{self.server.id}' needs you to sign in again: {oauth_error}",
                    details={"server_id": str(self.server.id), "reason": OAUTH_REAUTHORIZATION_REASON, "detail": str(oauth_error)},
                ) from self.error
            error_message = format_mcp_error(self.error)
            raise BadGatewayError(
                f"Failed to connect to server '{self.server.id}': {error_message}",
                details={"server_id": str(self.server.id), "reason": error_message},
            )

        if not self.session:
            await self.stop()
            raise BadGatewayError(
                f"Failed to connect to server '{self.server.id}': Session failed to initialize",
                details={
                    "server_id": str(self.server.id),
                    "reason": "Session failed to initialize",
                },
            )

        return self.session

    async def stop(self) -> None:
        """Signal worker to cleanly exit its context manager and wait for task completion."""
        self.stop_event.set()
        if self.task and not self.task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=5.0)
            except Exception as exc:
                logger.warning(f"Worker task cleanup warning for '{self.server.name}': {exc}")
                self.task.cancel()

    async def _run(self, timeout: float) -> None:
        """Run the MCP client lifecycle within a persistent task."""
        try:
            async with AsyncExitStack() as stack:
                if self.server.transport == TransportType.STDIO:
                    if not self.server.stdio_config:
                        raise ValueError("Missing stdio configuration")

                    validate_stdio_command(
                        self.server.stdio_config.command,
                        self.server.stdio_config.args,
                    )
                    sanitized_environment = sanitize_environment(self.server.stdio_config.env)

                    params = StdioServerParameters(
                        command=self.server.stdio_config.command,
                        args=self.server.stdio_config.args,
                        env=sanitized_environment,
                    )
                    logger.info(f"Spawning stdio process for '{self.server.name}': {params.command} {params.args}")
                    read_stream, write_stream = await stack.enter_async_context(stdio_client(params))

                elif self.server.transport == TransportType.STREAMABLE_HTTP:
                    if not self.server.http_config:
                        raise ValueError("Missing http configuration")

                    await validate_http_url_resolved(self.server.http_config.url)
                    logger.info(f"Connecting streamable-http client for '{self.server.name}' at {self.server.http_config.url}")
                    http_client = None
                    auth = self.auth or (self._oauth_auth() if self.server.auth_type == ServerAuthType.OAUTH else None)
                    if self.server.http_config.headers or auth is not None:
                        http_client = await stack.enter_async_context(
                            create_mcp_http_client(headers=self.server.http_config.headers or None, auth=auth)
                        )
                    read_stream, write_stream = await stack.enter_async_context(
                        streamable_http_client(self.server.http_config.url, http_client=http_client)
                    )
                else:
                    raise ValueError(f"Unsupported transport: {self.server.transport}")

                session = await stack.enter_async_context(ClientSession(read_stream, write_stream))

                # Initialize MCP protocol handshake
                await asyncio.wait_for(session.initialize(), timeout=timeout)

                self.session = session
                self.is_alive = True
                self.ready_event.set()
                logger.info(f"MCP SessionWorker started and initialized for '{self.server.name}'")

                # Block until stop is requested
                await self.stop_event.wait()
                logger.info(f"MCP SessionWorker stop received for '{self.server.name}'")

        except Exception as exc:
            logger.error(f"Error in SessionWorker for '{self.server.name}': {exc}")
            self.error = exc
            self.is_alive = False
            self.ready_event.set()
        finally:
            self.is_alive = False
            self.session = None

    def _oauth_auth(self) -> HubOAuthClientProvider:
        """Auth for an OAuth server: stored tokens, refreshed when expired. With no redirect handler, a token
        that cannot be refreshed raises OAuthFlowError, surfaced as a BadGatewayError with reason OAUTH_REAUTHORIZATION_REASON."""
        if self.oauth_credentials is None:
            raise ValueError("OAuth credentials storage is not configured")
        assert self.server.http_config is not None
        return HubOAuthClientProvider(
            server_url=self.server.http_config.url,
            client_metadata=build_client_metadata(self.settings, provider=None),
            storage=DbTokenStorage(self.server.id, self.server.user_id, self.oauth_credentials),
        )


class ConnectionManager:
    """Manages MCP client connections across stdio and streamable-http transports."""

    def __init__(self, oauth_credentials: OAuthCredentialRepositoryAbstract | None = None) -> None:
        self._oauth_credentials = oauth_credentials
        self._workers: dict[UUID, SessionWorker] = {}
        # One lock per Server, so a slow connect to one Server never blocks the others.
        self._locks: dict[UUID, asyncio.Lock] = {}
        self.settings = get_settings()

    async def get_or_create_session(
        self,
        server: ServerEntity,
        timeout: float | None = None,
    ) -> ClientSession:
        """Get an existing healthy session or create a new one."""
        if not server.enabled:
            raise BadRequestError(
                f"Server '{server.id}' is disabled. Enable it before performing this operation.",
                details={"server_id": str(server.id)},
            )

        async with self._lock_for(server.id):
            existing = self._workers.get(server.id)
            if existing and existing.is_alive and existing.session:
                if time.monotonic() - existing.last_verified_at < SESSION_PING_INTERVAL_SECONDS:
                    return existing.session
                try:
                    await asyncio.wait_for(existing.session.send_ping(), timeout=2.0)
                    existing.last_verified_at = time.monotonic()
                    return existing.session
                except Exception as exc:
                    logger.warning(f"Existing session for server '{server.name}' unhealthy: {exc}. Reconnecting...")
            if existing:
                await existing.stop()
                self._workers.pop(server.id, None)

            # Create new worker
            semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_EXECUTIONS_PER_SERVER)
            worker = SessionWorker(server=server, settings=self.settings, semaphore=semaphore, oauth_credentials=self._oauth_credentials)
            session = await worker.start(timeout=timeout)
            worker.last_verified_at = time.monotonic()
            self._workers[server.id] = worker
            return session

    async def disconnect(self, server_id: UUID) -> None:
        """Gracefully disconnect an active server session."""
        async with self._lock_for(server_id):
            worker = self._workers.pop(server_id, None)
            if worker:
                await worker.stop()
                logger.info(f"Disconnected session for server {server_id}")

    async def authorize(self, server: ServerEntity, auth: httpx2.Auth, timeout: float) -> None:
        """Run one OAuth sign-in (ADR-0008) for a server that is not saved yet: open a session with `auth`, whose
        callback handler waits for the user to approve access, initialize it, then close it. Raises as
        `get_or_create_session` does; the original OAuth error stays in the exception chain."""
        worker = SessionWorker(
            server=server,
            settings=self.settings,
            semaphore=asyncio.Semaphore(1),
            oauth_credentials=self._oauth_credentials,
            auth=auth,
        )
        try:
            await worker.start(timeout=timeout)
        finally:
            await worker.stop()

    async def test_connection(
        self,
        server: ServerEntity,
        timeout: float | None = None,
    ) -> tuple[bool, str, int, float]:
        """Test server connectivity and return (success, message, tools_count, latency_ms)."""
        start_time = time.perf_counter()
        connect_timeout = timeout or self.settings.DEFAULT_CONNECTION_TIMEOUT

        # Create an ephemeral worker for test to avoid interfering with persistent state
        semaphore = asyncio.Semaphore(1)
        worker = SessionWorker(server=server, settings=self.settings, semaphore=semaphore, oauth_credentials=self._oauth_credentials)

        try:
            session = await worker.start(timeout=connect_timeout)
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=connect_timeout)
            tool_count = len(tools_result.tools)
            latency_ms = (time.perf_counter() - start_time) * 1000
            await worker.stop()
            return (
                True,
                f"Successfully connected to '{server.name}'. Discovered {tool_count} tools.",
                tool_count,
                round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            await worker.stop()
            error_message = format_mcp_error(exc)
            logger.warning(f"Connection test failed for '{server.name}': {error_message}")
            return False, error_message, 0, round(latency_ms, 2)

    async def list_tools(
        self,
        server: ServerEntity,
        timeout: float | None = None,
    ) -> list[mcp_types.Tool]:
        """Fetch list of tools from the target server."""
        fetch_timeout = timeout or self.settings.DEFAULT_CONNECTION_TIMEOUT
        session = await self.get_or_create_session(server, timeout=fetch_timeout)
        try:
            result = await asyncio.wait_for(session.list_tools(), timeout=fetch_timeout)
            return result.tools
        except TimeoutError as exc:
            raise GatewayTimeoutError(
                f"Operation 'list_tools' timed out after {fetch_timeout} seconds",
                details={"operation": "list_tools", "timeout_seconds": fetch_timeout},
            ) from exc
        except Exception as exc:
            await self.disconnect(server.id)
            error_message = format_mcp_error(exc)
            raise BadGatewayError(
                f"Failed to list tools from server '{server.id}': {error_message}",
                details={"server_id": str(server.id), "reason": error_message},
            ) from exc

    async def call_tool(
        self,
        server: ServerEntity,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> mcp_types.CallToolResult:
        """Invoke a tool on the specified server under concurrency and timeout controls."""
        execution_timeout = timeout or self.settings.DEFAULT_EXECUTION_TIMEOUT
        session = await self.get_or_create_session(server, timeout=execution_timeout)

        worker = self._workers.get(server.id)
        semaphore = worker.semaphore if worker else asyncio.Semaphore(1)

        async with semaphore:
            try:
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=execution_timeout,
                )
                if isinstance(result, mcp_types.CallToolResult):
                    return result
                raise InternalServerError(
                    f"Execution error for tool '{tool_name}': Unexpected tool result type: {type(result)}",
                    details={
                        "tool_name": tool_name,
                        "reason": f"Unexpected tool result type: {type(result)}",
                    },
                )
            except TimeoutError as exc:
                logger.error(f"Execution of tool '{tool_name}' timed out after {execution_timeout}s")
                raise GatewayTimeoutError(
                    f"Tool '{tool_name}' execution timed out after {execution_timeout} seconds",
                    details={"tool_name": tool_name, "timeout_seconds": execution_timeout},
                ) from exc
            except Exception as exc:
                logger.error(f"Error executing tool '{tool_name}' on server '{server.name}': {exc}")
                if "connection" in str(exc).lower() or "pipe" in str(exc).lower() or "stream" in str(exc).lower():
                    await self.disconnect(server.id)
                raise InternalServerError(
                    f"Execution error for tool '{tool_name}': {exc}",
                    details={"tool_name": tool_name, "reason": str(exc)},
                ) from exc

    def get_active_session_count(self, user_id: UUID) -> int:
        """Return the number of live downstream sessions (only those on `user_id`'s Servers when given)."""
        return len([worker for worker in self._workers.values() if worker.is_alive and worker.server.user_id == user_id])

    async def shutdown(self) -> None:
        """Shutdown all active sessions and clean up resources."""
        logger.info(f"Shutting down ConnectionManager ({len(self._workers)} active sessions)...")
        workers = list(self._workers.values())
        self._workers.clear()
        self._locks.clear()
        await asyncio.gather(*(worker.stop() for worker in workers), return_exceptions=True)
        logger.info("ConnectionManager shutdown complete.")

    def _lock_for(self, server_id: UUID) -> asyncio.Lock:
        return self._locks.setdefault(server_id, asyncio.Lock())
