import { client } from '@/client/client.gen';

export type TimelineDays = 7 | 30 | 90;

export interface TimelineEntry {
  id: number;
  organization_id: number;
  customer_id: number | null;
  phone_e164: string;
  channel: string;
  event_type: string;
  title: string;
  summary: string | null;
  payload: Record<string, unknown>;
  workflow_run_id: number | null;
  conversation_id: number | null;
  transaction_id: number | null;
  correlation_id: string | null;
  journey_state: string | null;
  occurred_at: string;
  platform_event_id: number | null;
}

export interface CustomerTimeline {
  organization_id: number;
  customer_id: number | null;
  phone_e164: string;
  customer_uuid: string | null;
  full_name: string | null;
  journey_state: string;
  channels_active: string[];
  entries: TimelineEntry[];
  entry_count: number;
}

export interface JourneyState {
  journey_state: string;
  channels_active: string[];
  customer_id: number | null;
  phone_e164: string | null;
}

function extractError(response: { error?: unknown }, fallback: string): string {
  if (typeof response.error === 'object' && response.error !== null && 'detail' in response.error) {
    return String((response.error as { detail?: unknown }).detail);
  }
  return fallback;
}

export async function fetchTimelineStatus(): Promise<{ enabled: boolean }> {
  const response = await client.get({ url: '/api/v1/customer-timeline/status' });
  if (response.error) {
    return { enabled: false };
  }
  return response.data as { enabled: boolean };
}

export async function fetchCustomerTimeline(
  customerId: number,
  days: TimelineDays = 30,
): Promise<CustomerTimeline> {
  const response = await client.get({
    url: `/api/v1/customer-timeline/customers/${customerId}`,
    query: { days, limit: 200 },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load customer timeline'));
  }
  return response.data as CustomerTimeline;
}

export async function fetchPhoneTimeline(
  phoneE164: string,
  days: TimelineDays = 30,
): Promise<CustomerTimeline> {
  const encoded = encodeURIComponent(phoneE164);
  const response = await client.get({
    url: `/api/v1/customer-timeline/phone/${encoded}`,
    query: { days, limit: 200 },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load phone timeline'));
  }
  return response.data as CustomerTimeline;
}

export async function fetchJourneyState(params: {
  customerId?: number;
  phoneE164?: string;
}): Promise<JourneyState> {
  const response = await client.get({
    url: '/api/v1/customer-timeline/journey-state',
    query: {
      customer_id: params.customerId,
      phone_e164: params.phoneE164,
    },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load journey state'));
  }
  return response.data as JourneyState;
}

export const JOURNEY_STATE_LABELS: Record<string, string> = {
  unknown: 'Unknown',
  idle: 'Idle',
  voice_active: 'On a call',
  voice_completed: 'Call completed',
  awaiting_payment: 'Awaiting payment',
  payment_pending: 'Payment pending',
  payment_completed: 'Payment received',
  payment_failed: 'Payment failed',
  whatsapp_follow_up: 'WhatsApp follow-up',
  email_follow_up: 'Email follow-up',
  campaign_retry: 'Campaign retry scheduled',
  escalated: 'Escalated to agent',
  orchestration_waiting: 'Workflow in progress',
};

export const CHANNEL_LABELS: Record<string, string> = {
  voice: 'Voice',
  whatsapp: 'WhatsApp',
  email: 'Email',
  payment: 'Payment',
  campaign: 'Campaign',
  escalation: 'Escalation',
  orchestration: 'Orchestration',
  system: 'System',
};
