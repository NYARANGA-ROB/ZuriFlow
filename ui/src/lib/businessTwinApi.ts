import { client } from '@/client/client.gen';

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

export async function fetchBusinessHealth() {
  return api<{
    overall_freshness: number;
    sections: Record<string, { label: string; state: string; pending?: number }>;
    pending_changes: number;
    conflicts: number;
    alerts: Array<{ id: number; title: string; body: string; severity: string }>;
    profile: Record<string, unknown>;
  }>('/business/health');
}

export async function fetchBusinessChanges() {
  return api<{
    changes: Array<{
      id: number;
      field: string;
      old_value: string | null;
      new_value: string | null;
      source: string;
      confidence: number;
      risk: string;
      status: string;
    }>;
    conflicts: Array<{
      id: number;
      field: string;
      source_a: string;
      value_a: string | null;
      source_b: string;
      value_b: string | null;
    }>;
    failed_syncs: Array<{ id: number; status: string; error: string | null }>;
  }>('/business/changes');
}

export async function decideChange(id: number, decision: string) {
  return api(`/business/changes/${id}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
  });
}

export async function importWebsite(url: string) {
  return api('/business/website/import', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export async function sendInterview(transcript: string) {
  return api('/business/interview', {
    method: 'POST',
    body: JSON.stringify({ transcript, turn_index: 0 }),
  });
}

export async function saveBusinessProfile(payload: Record<string, unknown>) {
  return api('/business/profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
