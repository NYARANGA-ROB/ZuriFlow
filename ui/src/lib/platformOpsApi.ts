import { client } from '@/client/client.gen';

export interface PlatformEventStatus {
  enabled: boolean;
  registered_handlers: string[];
}

export interface PlatformEvent {
  event_id: string;
  event_type: string;
  organization_id: number | null;
  source: string;
  correlation_id: string | null;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface PlatformObservability {
  organization_id: number;
  counters: Record<string, number>;
  last_published_at: number | null;
}

export interface DeadLetterEntry {
  event_id?: string;
  event_type?: string;
  reason?: string;
  failed_at?: string;
  [key: string]: unknown;
}

export interface DurableExecutionStatus {
  enabled: boolean;
  definitions: string[];
}

function extractError(response: { error?: unknown }, fallback: string): string {
  if (typeof response.error === 'object' && response.error !== null && 'detail' in response.error) {
    return String((response.error as { detail?: unknown }).detail);
  }
  return fallback;
}

export async function fetchPlatformEventsStatus(): Promise<PlatformEventStatus> {
  const response = await client.get({ url: '/api/v1/platform-events/status' });
  if (response.error) {
    return { enabled: false, registered_handlers: [] };
  }
  return response.data as PlatformEventStatus;
}

export async function listPlatformEvents(params: {
  organizationId: number;
  days?: number;
  eventType?: string;
  correlationId?: string;
  limit?: number;
}): Promise<PlatformEvent[]> {
  const response = await client.get({
    url: '/api/v1/platform-events/events',
    query: {
      organization_id: params.organizationId,
      days: params.days ?? 7,
      event_type: params.eventType,
      correlation_id: params.correlationId,
      limit: params.limit ?? 100,
    },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load platform events'));
  }
  return response.data as PlatformEvent[];
}

export async function fetchPlatformObservability(
  organizationId: number,
): Promise<PlatformObservability> {
  const response = await client.get({
    url: '/api/v1/platform-events/observability',
    query: { organization_id: organizationId },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load observability'));
  }
  return response.data as PlatformObservability;
}

export async function listDeadLetterEvents(
  organizationId: number,
  limit = 50,
): Promise<DeadLetterEntry[]> {
  const response = await client.get({
    url: '/api/v1/platform-events/dead-letter',
    query: { organization_id: organizationId, limit },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load dead letter queue'));
  }
  return response.data as DeadLetterEntry[];
}

export async function fetchDurableExecutionStatus(): Promise<DurableExecutionStatus> {
  const response = await client.get({ url: '/api/v1/durable-orchestrations/status' });
  if (response.error) {
    return { enabled: false, definitions: [] };
  }
  return response.data as DurableExecutionStatus;
}

export async function processPlatformEventRetries(organizationId: number): Promise<{
  queued: boolean;
  job_id: string | null;
}> {
  const response = await client.post({
    url: '/api/v1/platform-events/retries/process',
    query: { organization_id: organizationId },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to queue retries'));
  }
  return response.data as { queued: boolean; job_id: string | null };
}

export interface OrchestrationSummary {
  id: number;
  organization_id: number;
  definition_name: string;
  orchestration_key: string;
  status: string;
  current_step: string;
  workflow_run_id: number | null;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}

export interface OrchestrationDetail {
  orchestration_id: number;
  organization_id: number;
  definition_name: string;
  orchestration_key: string;
  status: string;
  current_step: string;
  state: Record<string, unknown>;
  error_message: string | null;
}

export interface OrchestrationEvent {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export async function listOrchestrations(params: {
  status?: string;
  definitionName?: string;
  limit?: number;
  offset?: number;
}): Promise<OrchestrationSummary[]> {
  const response = await client.get({
    url: '/api/v1/durable-orchestrations',
    query: {
      status: params.status,
      definition_name: params.definitionName,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load orchestrations'));
  }
  return response.data as OrchestrationSummary[];
}

export async function getOrchestration(orchestrationId: number): Promise<OrchestrationDetail> {
  const response = await client.get({
    url: `/api/v1/durable-orchestrations/${orchestrationId}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Orchestration not found'));
  }
  return response.data as OrchestrationDetail;
}

export async function listOrchestrationEvents(
  orchestrationId: number,
  limit = 100,
): Promise<OrchestrationEvent[]> {
  const response = await client.get({
    url: `/api/v1/durable-orchestrations/${orchestrationId}/events`,
    query: { limit },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load orchestration events'));
  }
  return response.data as OrchestrationEvent[];
}

export async function resumeOrchestration(orchestrationId: number): Promise<OrchestrationDetail> {
  const response = await client.post({
    url: `/api/v1/durable-orchestrations/${orchestrationId}/resume`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to resume orchestration'));
  }
  return response.data as OrchestrationDetail;
}

export async function replayPlatformEvents(params: {
  organizationId: number;
  eventType?: string;
  days?: number;
  limit?: number;
}): Promise<{ replayed: number; failed: number; total: number }> {
  const response = await client.post({
    url: '/api/v1/platform-events/replay',
    query: {
      organization_id: params.organizationId,
      event_type: params.eventType,
      days: params.days ?? 7,
      limit: params.limit ?? 100,
    },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to replay events'));
  }
  return response.data as { replayed: number; failed: number; total: number };
}

export async function replayPlatformEvent(eventId: string): Promise<{
  replayed: number;
  failed: number;
  total: number;
}> {
  const response = await client.post({
    url: `/api/v1/platform-events/replay/${encodeURIComponent(eventId)}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to replay event'));
  }
  return response.data as { replayed: number; failed: number; total: number };
}

export async function publishPlatformEvent(input: {
  event_type: string;
  payload?: Record<string, unknown>;
  correlation_id?: string | null;
  route_async?: boolean;
}): Promise<{ published: boolean; event_id: string | null }> {
  const response = await client.post({
    url: '/api/v1/platform-events/publish',
    body: input,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to publish event'));
  }
  return response.data as { published: boolean; event_id: string | null };
}
