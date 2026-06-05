import { HttpStatus } from '@nestjs/common';

export type UnifiedErrorCode =
  | 'UPSTREAM_TIMEOUT'
  | 'UPSTREAM_UNAVAILABLE'
  | 'UPSTREAM_HTTP_ERROR'
  | 'BAD_GATEWAY'
  | 'INTERNAL_ERROR';

export interface UnifiedError {
  code: UnifiedErrorCode;
  message: string;
  http_status: number;
  request_id: string;
  retryable: boolean;
  degraded: boolean;
  details: Record<string, unknown>;
}

export interface SidecarErrorContext {
  upstreamService: string;
  upstreamPath: string;
  timeoutMs: number;
  retryBudget: number;
  attemptsUsed: number;
  statusCode?: number;
  reason?: string;
  upstreamBody?: unknown;
  originalMessage?: string;
}

export function createUnifiedError(
  requestId: string,
  context: SidecarErrorContext,
): UnifiedError {
  const statusCode = context.statusCode;
  const isTimeout = context.reason === 'timeout';
  const isUnavailable = context.reason === 'unavailable';
  const isUpstreamHttp = typeof statusCode === 'number';

  let code: UnifiedErrorCode = 'INTERNAL_ERROR';
  let httpStatus = HttpStatus.INTERNAL_SERVER_ERROR;
  let retryable = false;
  let message = 'Unexpected upstream failure';

  if (isTimeout) {
    code = 'UPSTREAM_TIMEOUT';
    httpStatus = HttpStatus.GATEWAY_TIMEOUT;
    retryable = true;
    message = `Upstream request timed out after ${context.timeoutMs}ms`;
  } else if (isUnavailable) {
    code = 'UPSTREAM_UNAVAILABLE';
    httpStatus = HttpStatus.SERVICE_UNAVAILABLE;
    retryable = true;
    message = 'Upstream service unavailable';
  } else if (isUpstreamHttp) {
    code = 'UPSTREAM_HTTP_ERROR';
    httpStatus = HttpStatus.BAD_GATEWAY;
    retryable = statusCode >= 500;
    message = `Upstream service returned HTTP ${statusCode}`;
  } else {
    code = 'BAD_GATEWAY';
    httpStatus = HttpStatus.BAD_GATEWAY;
    retryable = true;
    message = context.originalMessage || 'Failed to communicate with upstream service';
  }

  return {
    code,
    message,
    http_status: httpStatus,
    request_id: requestId,
    retryable,
    degraded: true,
    details: {
      upstream_service: context.upstreamService,
      upstream_path: context.upstreamPath,
      timeout_ms: context.timeoutMs,
      retry_budget: context.retryBudget,
      attempts_used: context.attemptsUsed,
      upstream_status: statusCode ?? null,
      upstream_reason: context.reason ?? null,
      upstream_error: context.originalMessage ?? null,
      upstream_body: context.upstreamBody ?? null,
    },
  };
}
