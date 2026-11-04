import { client } from '@/client/client.gen';

export type IntelligenceCapabilities = {
  enabled: boolean;
  payments: boolean;
  conversation_excerpts: boolean;
  dashboards: string[];
};

export type IntelligenceInsight = {
  kind: string;
  severity: string;
  headline: string;
  detail?: string;
};

export type IntelligenceDashboard = {
  dashboard: string;
  kpis: Record<string, unknown>;
  insights?: IntelligenceInsight[];
  intent_distribution?: Record<string, number>;
  top_products?: Array<[string, number]>;
  conversations?: Array<Record<string, string | number | null>>;
  restricted?: boolean;
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

export async function fetchIntelligenceStatus(): Promise<IntelligenceCapabilities> {
  return api('/business-intelligence/status');
}

export async function fetchIntelligenceDashboard(
  name: string,
  organizationId: number,
  days = 7,
): Promise<IntelligenceDashboard> {
  return api(
    `/business-intelligence/dashboards/${name}?organization_id=${organizationId}&days=${days}`,
  );
}
