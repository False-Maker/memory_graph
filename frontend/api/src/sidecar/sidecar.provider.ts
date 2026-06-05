import { Provider } from '@nestjs/common';
import {
  SIDECAR_CLIENT,
  SidecarClient,
  SidecarRequestError,
  SidecarRequestContext,
  SidecarTimeoutPolicy,
} from './sidecar-client';

const DEFAULT_BACKEND_BASE_URL = (
  process.env.BACKEND_BASE_URL ??
  process.env.MEMORY_GRAPH_BACKEND_URL ??
  'http://127.0.0.1:8000'
).replace(/\/$/, '');
const BACKEND_HEALTH_PATH = process.env.BACKEND_HEALTH_PATH ?? '/health';

function getBackendHealthUrl(): string {
  return `${DEFAULT_BACKEND_BASE_URL}${BACKEND_HEALTH_PATH.startsWith('/') ? '' : '/'}${BACKEND_HEALTH_PATH}`;
}

async function readUpstreamBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  try {
    return await response.text();
  } catch {
    return null;
  }
}

class BackendHealthSidecarClient implements SidecarClient {
  async ping(
    request: SidecarRequestContext,
    policy: SidecarTimeoutPolicy,
  ): Promise<boolean> {
    const maxAttempts = Math.max(1, policy.retryBudget + 1);
    const upstreamUrl = getBackendHealthUrl();

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), policy.timeoutMs);

      try {
        const response = await fetch(upstreamUrl, {
          method: 'GET',
          headers: {
            Accept: 'application/json',
            'x-request-id': request.requestId,
          },
          signal: controller.signal,
        });

        if (!response.ok) {
          const upstreamBody = await readUpstreamBody(response);
          throw new SidecarRequestError({
            upstreamService: 'memory-graph-backend',
            upstreamPath: BACKEND_HEALTH_PATH,
            timeoutMs: policy.timeoutMs,
            retryBudget: policy.retryBudget,
            attemptsUsed: attempt,
            statusCode: response.status,
            reason: 'upstream_http',
            upstreamBody,
            originalMessage: `Backend health probe failed with status ${response.status}`,
          });
        }

        const payload = await readUpstreamBody(response);
        if (
          payload &&
          typeof payload === 'object' &&
          'status' in payload &&
          payload.status !== 'healthy'
        ) {
          throw new SidecarRequestError({
            upstreamService: 'memory-graph-backend',
            upstreamPath: BACKEND_HEALTH_PATH,
            timeoutMs: policy.timeoutMs,
            retryBudget: policy.retryBudget,
            attemptsUsed: attempt,
            reason: 'upstream_http',
            upstreamBody: payload,
            originalMessage: 'Backend health endpoint returned a non-healthy status',
          });
        }

        return true;
      } catch (error) {
        const isAbort = error instanceof Error && error.name === 'AbortError';
        const shouldRetry = attempt < maxAttempts && (isAbort || !(error instanceof SidecarRequestError));

        if (shouldRetry) {
          continue;
        }

        if (error instanceof SidecarRequestError) {
          throw error;
        }

        throw new SidecarRequestError({
          upstreamService: 'memory-graph-backend',
          upstreamPath: BACKEND_HEALTH_PATH,
          timeoutMs: policy.timeoutMs,
          retryBudget: policy.retryBudget,
          attemptsUsed: attempt,
          reason: isAbort ? 'timeout' : 'network',
          originalMessage: error instanceof Error ? error.message : String(error),
        });
      } finally {
        clearTimeout(timeout);
      }
    }

    return false;
  }
}

export const sidecarClientProvider: Provider = {
  provide: SIDECAR_CLIENT,
  useClass: BackendHealthSidecarClient,
};
