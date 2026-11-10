/**
 * Domain and API Types for MCP Hub Frontend
 * Mirrors FastAPI backend schemas in backend/app/schemas/
 */

export type TransportType = "stdio" | "streamable-http";

export type ServerHealthStatus = "UNKNOWN" | "HEALTHY" | "UNHEALTHY" | "CONNECTING" | "DISCONNECTED";

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
export type ToolCallStatus = "running" | "completed" | "failed" | "rejected";

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
