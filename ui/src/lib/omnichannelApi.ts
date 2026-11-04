import { client } from '@/client/client.gen';

export type EngagementDashboard = {
  enabled: boolean;
  days: number;
  messages_sent: number;
  delivery_rate: number;
  response_rate: number;
  channel_conversion: {
    conversations: number;
    voice_to_whatsapp: number;
    voice_to_whatsapp_rate: number;
    payment_conversions: number;
    payment_conversion_rate: number;
  };
  by_channel: Array<{
    channel: string;
    messages_sent: number;
    delivered: number;
    failed: number;
    replies: number;
    delivery_rate: number;
    response_rate: number;
  }>;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const base = client.getConfig().baseUrl ?? '';
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  const auth = client.getConfig().headers as Record<string, string> | undefined;
  if (auth?.Authorization) {
    headers.set('Authorization', auth.Authorization);
  }
  const res = await fetch(`${base}/api/v1${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function fetchEngagementStatus(): Promise<{ enabled: boolean }> {
  return api('/omnichannel/status');
}

export async function fetchEngagementDashboard(days = 30): Promise<EngagementDashboard> {
  return api(`/omnichannel/dashboard?days=${days}`);
}
