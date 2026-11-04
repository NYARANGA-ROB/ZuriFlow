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
  if (res.status === 204) {
    return {} as T;
  }
  return res.json() as Promise<T>;
}

export type SetupProfile = {
  business_name?: string | null;
  industry?: string | null;
  location?: string | null;
  county?: string | null;
  business_hours?: {
    timezone: string;
    weekdays: string;
    saturday?: string | null;
    sunday?: string | null;
  };
  phone_numbers?: Array<{ label: string; number: string; purpose: string }>;
  languages?: string[];
  payment?: {
    mpesa_enabled: boolean;
    paybill?: string | null;
    till_number?: string | null;
    account_reference?: string | null;
  };
  escalation_contacts?: Array<{ name: string; phone: string; role: string }>;
  channels?: { voice: boolean; sms: boolean; whatsapp: boolean; email: boolean };
};

export type KnowledgeEntry = {
  id: number;
  category: string;
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  document_uuid?: string | null;
  is_active: boolean;
  updated_at?: string | null;
};

export type AuditItem = {
  id: number;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  summary?: string | null;
  actor_user_id?: number | null;
  created_at: string;
};

export async function fetchSetup() {
  return api<{
    profile: SetupProfile;
    completeness: { steps: Record<string, boolean>; completed: number; total: number; ready: boolean };
    counties: string[];
    industries: string[];
  }>('/control-plane/setup');
}

export async function saveSetup(profile: SetupProfile) {
  return api<{ profile: SetupProfile; completeness: { ready: boolean } }>('/control-plane/setup', {
    method: 'PUT',
    body: JSON.stringify(profile),
  });
}

export async function fetchKnowledge(category?: string) {
  const qs = category ? `?category=${encodeURIComponent(category)}` : '';
  return api<{ categories: string[]; entries: KnowledgeEntry[] }>(`/control-plane/knowledge${qs}`);
}

export async function createKnowledge(entry: {
  category: string;
  title: string;
  content: string;
  document_uuid?: string;
}) {
  return api<KnowledgeEntry>('/control-plane/knowledge', {
    method: 'POST',
    body: JSON.stringify(entry),
  });
}

export async function searchKnowledge(q: string) {
  return api<{ query: string; results: Array<{ text: string; category?: string }>; total_results: number }>(
    `/control-plane/knowledge/search?q=${encodeURIComponent(q)}`,
  );
}

export async function fetchBusinessTools() {
  return api<{ tools: Array<{ key: string; name: string; description: string; kind: string }> }>(
    '/control-plane/business-tools',
  );
}

export async function installBusinessTool(key: string, endpoint_url?: string) {
  return api<Record<string, unknown>>('/control-plane/business-tools/install', {
    method: 'POST',
    body: JSON.stringify({ key, endpoint_url }),
  });
}

export async function fetchWorkflowBuilder() {
  return api<{
    reusable_nodes: Array<{ key: string; label: string; type: string; prompt: string }>;
    templates: Array<{ key: string; name: string; description: string }>;
    variables: Array<{ name: string; description: string }>;
    environments: string[];
  }>('/control-plane/workflow-builder');
}

export async function promoteWorkflow(workflowId: number, target: string, changelog: string) {
  return api(`/control-plane/workflows/${workflowId}/promote`, {
    method: 'POST',
    body: JSON.stringify({ target, changelog }),
  });
}

export async function rollbackWorkflow(workflowId: number, definitionId: number, changelog: string) {
  return api(`/control-plane/workflows/${workflowId}/rollback`, {
    method: 'POST',
    body: JSON.stringify({ definition_id: definitionId, changelog }),
  });
}

export async function fetchAuditLogs() {
  return api<{ items: AuditItem[] }>('/control-plane/audit-logs');
}
