export const SIDECAR_CLIENT = Symbol('SIDECAR_CLIENT');

export interface SidecarTimeoutPolicy {
  timeoutMs: number;
  retryBudget: number;
}

export interface SidecarRequestContext {
  requestId: string;
}

export interface SidecarRequestErrorContext {
  upstreamService: string;
  upstreamPath: string;
  timeoutMs: number;
  retryBudget: number;
  attemptsUsed: number;
  statusCode?: number;
  reason?: 'timeout' | 'unavailable' | 'upstream_http' | 'network';
  upstreamBody?: unknown;
  originalMessage?: string;
}

export class SidecarRequestError extends Error {
  constructor(public readonly context: SidecarRequestErrorContext) {
    super(context.originalMessage ?? 'Sidecar request failed');
    this.name = 'SidecarRequestError';
  }
}

export interface SidecarClient {
  ping(
    request: SidecarRequestContext,
    policy: SidecarTimeoutPolicy,
  ): Promise<boolean>;
}
