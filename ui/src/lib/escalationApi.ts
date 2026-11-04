import { client } from '@/client/client.gen';

export interface EscalationDashboard {
  organization_id: number;
  queue_depths: Record<string, number>;
  pending_count: number;
  pending: Array<{
    session_id: string;
    handoff: HandoffPackage;
    queue_position?: number;
    claimed?: boolean;
    claim?: Record<string, unknown> | null;
  }>;
}

export interface HandoffPackage {
  session_id: string;
  organization_id: number;
  workflow_run_id: number;
  phone_e164: string;
  customer_name: string;
  customer_id: number | null;
  intent: string;
  reason: string;
  language: string;
  summary: string;
  transcript_excerpt: Array<Record<string, unknown>>;
  slots: Record<string, string>;
  priority: number;
  risk_level: string;
  call_sid: string;
  queue_name: string;
  metadata: Record<string, unknown>;
}

export interface OperatorClaim {
  session_id: string;
  organization_id: number;
  queue_name: string;
  operator_id: number;
  claimed_at: number;
  handoff: HandoffPackage;
}

function extractError(response: { error?: unknown }, fallback: string): string {
  if (typeof response.error === 'object' && response.error !== null && 'detail' in response.error) {
    return String((response.error as { detail?: unknown }).detail);
  }
  return fallback;
}

export async function fetchEscalationStatus(): Promise<{ enabled: boolean }> {
  const response = await client.get({ url: '/api/v1/human-escalation/status' });
  if (response.error) return { enabled: false };
  return response.data as { enabled: boolean };
}

export async function fetchEscalationDashboard(): Promise<EscalationDashboard> {
  const response = await client.get({ url: '/api/v1/human-escalation/dashboard' });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load escalation dashboard'));
  }
  return response.data as EscalationDashboard;
}

export async function claimEscalation(queueName = 'human'): Promise<OperatorClaim | null> {
  const response = await client.post({
    url: '/api/v1/human-escalation/claim',
    body: { queue_name: queueName },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to claim escalation'));
  }
  return (response.data as OperatorClaim | null) ?? null;
}

export async function getHandoff(sessionId: string): Promise<HandoffPackage> {
  const response = await client.get({
    url: `/api/v1/human-escalation/handoff/${encodeURIComponent(sessionId)}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Handoff not found'));
  }
  return response.data as HandoffPackage;
}

export async function resolveEscalation(sessionId: string): Promise<{ resolved: boolean }> {
  const response = await client.post({
    url: `/api/v1/human-escalation/handoff/${encodeURIComponent(sessionId)}/resolve`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to resolve escalation'));
  }
  return response.data as { resolved: boolean };
}

export async function transferHandoff(
  sessionId: string,
  destination?: string,
): Promise<Record<string, unknown>> {
  const response = await client.post({
    url: `/api/v1/human-escalation/handoff/${encodeURIComponent(sessionId)}/transfer`,
    body: { destination },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Transfer failed'));
  }
  return response.data as Record<string, unknown>;
}
