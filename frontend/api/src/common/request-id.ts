import { randomUUID } from 'node:crypto';

export const REQUEST_ID_HEADER = 'x-request-id';

const REQUEST_ID_PATTERN = /^[a-zA-Z0-9._:-]{8,128}$/;

export function normalizeRequestId(input?: string | string[]): string {
  const raw = Array.isArray(input) ? input[0] : input;
  const candidate = typeof raw === 'string' ? raw.trim() : '';

  if (candidate && REQUEST_ID_PATTERN.test(candidate)) {
    return candidate;
  }

  return randomUUID();
}
