import { client } from '@/client/client.gen';

export interface ReliabilityStatus {
  enabled: boolean;
  max_retries: number;
  retry_base_delay_s: number;
  event_ttl_s: number;
  dlq_ttl_s: number;
  ws_checkpoint_ttl_s: number;
  features: string[];
}

export interface FailureSummary {
  organization_id: number;
  days: number;
  totals: Record<string, number>;
  recent_failures: Array<Record<string, unknown>>;
}

function extractError(response: { error?: unknown }, fallback: string): string {
  if (typeof response.error === 'object' && response.error !== null && 'detail' in response.error) {
    return String((response.error as { detail?: unknown }).detail);
  }
  return fallback;
}

export async function fetchReliabilityStatus(): Promise<ReliabilityStatus> {
  const response = await client.get({ url: '/api/v1/call-reliability/status' });
  if (response.error) {
    return {
      enabled: false,
      max_retries: 0,
      retry_base_delay_s: 0,
      event_ttl_s: 0,
      dlq_ttl_s: 0,
      ws_checkpoint_ttl_s: 0,
      features: [],
    };
  }
  return response.data as ReliabilityStatus;
}

export async function fetchFailureSummary(
  organizationId: number,
  days = 7,
): Promise<FailureSummary> {
  const response = await client.get({
    url: '/api/v1/call-reliability/failures/summary',
    query: { organization_id: organizationId, days },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load failure summary'));
  }
  return response.data as FailureSummary;
}

export async function listRetryQueue(organizationId: number, limit = 50) {
  const response = await client.get({
    url: '/api/v1/call-reliability/retry-queue',
    query: { organization_id: organizationId, limit },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load retry queue'));
  }
  return response.data as Array<Record<string, unknown>>;
}

export async function listReliabilityDlq(organizationId: number, limit = 50) {
  const response = await client.get({
    url: '/api/v1/call-reliability/dead-letter',
    query: { organization_id: organizationId, limit },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load dead letter queue'));
  }
  return response.data as Array<Record<string, unknown>>;
}

export async function processRetryQueue(organizationId: number) {
  const response = await client.post({
    url: '/api/v1/call-reliability/retry-queue/process',
    query: { organization_id: organizationId },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to queue retries'));
  }
  return response.data as { queued: boolean; job_id: string | null };
}

export async function replaySession(sessionId: string) {
  const response = await client.post({
    url: `/api/v1/call-reliability/replay/sessions/${encodeURIComponent(sessionId)}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Replay failed'));
  }
  return response.data as { replayed: number; failed: number; skipped: number; total: number };
}

export async function replayWorkflowRun(workflowRunId: number) {
  const response = await client.post({
    url: `/api/v1/call-reliability/replay/workflows/${workflowRunId}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Replay failed'));
  }
  return response.data as { replayed: number; failed: number; skipped: number; total: number };
}
