/**
 * Domain and API Types for MCP Hub Frontend
 * Mirrors FastAPI backend schemas in backend/app/schemas/
 */

export type TransportType = "stdio" | "streamable-http";

/** `NEEDS_AUTH`: an OAuth server whose tokens can no longer be refreshed; the user must sign in again. */
export type ServerHealthStatus = "UNKNOWN" | "HEALTHY" | "UNHEALTHY" | "DISCONNECTED" | "NEEDS_AUTH";

/** How the hub authenticates to the server: `oauth` = connected through a provider sign-in. */
export type ServerAuthType = "none" | "oauth";

export interface StdioConfig {
    command: string;
    args?: string[];
    env?: Record<string, string>;
}

export interface HttpConfig {
    url: string;
    headers?: Record<string, string>;
}

export interface ConnectionConfigRead {
    command?: string | null;
    args?: string[] | null;
    url?: string | null;
    headers?: Record<string, string> | null;
}

export interface ServerRead {
    id: string;
    name: string;
    description?: string | null;
    transport: TransportType;
    connection_config: ConnectionConfigRead;
    enabled: boolean;
    health_status: ServerHealthStatus;
    last_connected_at?: string | null;
    last_health_check_at?: string | null;
    discovered_tool_count: number;
    /** Optional so older responses (and fixtures) without it read as `none`. */
    auth_type?: ServerAuthType;
    oauth_provider_id?: string | null;
    created_at: string;
    updated_at: string;
}

export interface ServerCreate {
    name: string;
    description?: string | null;
    transport: TransportType;
    enabled: boolean;
    stdio_config?: StdioConfig;
    http_config?: HttpConfig;
}

export interface ServerUpdate {
    name?: string | null;
    description?: string | null;
    transport?: TransportType | null;
    stdio_config?: StdioConfig | null;
    http_config?: HttpConfig | null;
    enabled?: boolean | null;
}

export interface ServerTestResponse {
    success: boolean;
    message: string;
    tools_count: number;
    latency_ms: number;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface ServerFilterParams {
    page?: number;
    page_size?: number;
    enabled?: boolean;
    transport?: TransportType;
    health_status?: ServerHealthStatus;
    search?: string;
    sort_by?: "created_at" | "name" | "updated_at" | "discovered_tool_count";
    sort_order?: "asc" | "desc";
}

export interface ToolRead {
    id: string; // server_id:tool_name
    name: string;
    description?: string | null;
    input_schema: Record<string, any>;
    server_id: string;
    server_name: string;
    availability_status: "AVAILABLE" | "UNAVAILABLE" | string;
    last_discovered_at: string;
}

export interface ToolFilterParams {
    page?: number;
    page_size?: number;
    server_id?: string;
    tool_name?: string;
    status?: string;
    search?: string;
}

export interface ToolExecuteRequest {
    arguments: Record<string, any>;
}

export interface ToolContentItem {
    type: string;
    text?: string | null;
    data?: any;
}

export interface ToolExecuteResponse {
    execution_id: string;
    server_id: string;
    tool_name: string;
    is_error: boolean;
    content: ToolContentItem[];
    structured_content?: any;
    duration_ms: number;
    executed_at: string;
}

export interface ExecutionResponsePayload {
    content?: ToolContentItem[];
    structured_content?: any;
    [key: string]: any;
}

export interface ExecutionRecord {
    id: string;
    server_id: string;
    server_name: string;
    tool_name: string;
    arguments: Record<string, any>;
    is_error: boolean;
    /** Recorded status; `rejected` = refused by the hub before reaching the downstream Server (ADR-0002). */
    status?: ToolCallStatus | string;
    error_message?: string | null;
    duration_ms: number;
    executed_at: string;
    response?: ExecutionResponsePayload | null;
}

export interface ExecutionFilterParams {
    page?: number;
    page_size?: number;
    server_id?: string;
    tool_name?: string;
    is_error?: boolean;
    status?: string;
}

export interface HealthResponse {
    status: string;
    version: string;
    timestamp: string;
}

export interface ReadyResponse {
    status: string;
    checks: Record<string, boolean>;
    timestamp: string;
}

export interface MetricsResponse {
    active_sessions: number;
    total_servers: number;
    healthy_servers: number;
    total_executions: number;
    uptime_seconds: number;
}

export interface ApiErrorDetail {
    code: string;
    message: string;
    details?: any;
}

export interface ApiErrorResponse {
    error: ApiErrorDetail;
}

export type SessionStatus = "active" | "completed" | "failed";
export type ToolCallStatus = "completed" | "failed" | "rejected";

export interface SessionRead {
    id: string;
    title?: string | null;
    status: SessionStatus | string;
    created_at: string;
    last_activity_at: string;
    total_tool_calls: number;
}

export interface SessionDetailRead {
    id: string;
    title?: string | null;
    metadata?: Record<string, any> | null;
    status: SessionStatus | string;
    created_at: string;
    last_activity_at: string;
    total_tool_calls: number;
    successful_tool_calls: number;
    failed_tool_calls: number;
    rejected_tool_calls: number;
}

export interface ToolCallRead {
    id: string;
    session_id?: string | null;
    server_name: string;
    tool_name: string;
    status: ToolCallStatus | string;
    started_at: string;
    completed_at?: string | null;
    duration_ms?: number | null;
    error_summary?: string | null;
    arguments: Record<string, any>;
    response?: any | null;
}

export interface SessionFilterParams {
    page?: number;
    page_size?: number;
    search?: string;
    status?: string;
}

export interface SessionToolCallFilterParams {
    page?: number;
    page_size?: number;
    sort_by?: string;
    order?: "asc" | "desc";
    status?: string;
    server_name?: string;
    tool_name?: string;
}

// --- Accounts & API keys ---

export interface RegisterRequest {
    email: string;
    password: string;
}

export interface LoginRequest {
    email: string;
    password: string;
}

export interface TokenResponse {
    access_token: string;
    token_type: string;
    expires_in: number;
}

export interface UserRead {
    id: string;
    email: string;
    created_at: string;
}

export interface ApiKeyRead {
    id: string;
    name: string;
    key_prefix: string;
    created_at: string;
    last_used_at?: string | null;
    revoked_at?: string | null;
    /** Minutes without a tool call before a Session opened with this key is completed; null = the 30-minute default. Not key expiry. */
    session_idle_minutes?: number | null;
}

/** Returned once, on creation: the only time the full key is available. */
export interface ApiKeyCreated extends ApiKeyRead {
    key: string;
}

/** A server's tool as one API key sees it. Tools are visible by default; `enabled: false` hides it from that key. */
export interface ApiKeyTool {
    tool_id: string;
    name: string;
    description: string | null;
    enabled: boolean;
}

export interface ApiKeyToolVisibility {
    tool_name: string;
    enabled: boolean;
}

// --- OAuth provider connections ---

/** A hosted MCP server from the backend's provider catalog that can be connected with an OAuth sign-in. */
export interface OAuthProvider {
    id: string;
    name: string;
    description: string;
    category: string;
    mcp_url: string;
    docs_url: string;
    logo?: string | null;
    /** False when the provider needs a pre-registered OAuth client the admin hasn't configured. */
    available: boolean;
    /** The setting that configures the provider's OAuth client, when it needs one. */
    client_env?: string | null;
    /** How many servers this user has already connected through this provider. */
    connected_count: number;
}

export interface OAuthConnectRequest {
    provider_id: string;
    name?: string;
}

export interface OAuthAuthorizationResponse {
    /** Null when the server needed no sign-in: it is already registered as `server_id`. */
    authorization_url: string | null;
    state: string | null;
    server_id?: string | null;
}

/** Posted by `/oauth/complete` (the popup) to the window that opened it. */
export interface OAuthCompleteMessage {
    type: "mcp-hub-oauth";
    status: "success" | "error";
    server_id?: string | null;
    error?: string | null;
}
