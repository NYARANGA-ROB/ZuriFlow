import { client } from '@/client/client.gen';

export type AnalyticsDays = 7 | 30;

export interface AdminSummary {
  organization_id: number;
  from_ts: number;
  to_ts: number;
  generated_at: number;
  live_calls?: {
    active_count?: number;
    calls?: Array<Record<string, unknown>>;
  };
  tenant?: {
    total_calls?: number;
    member_count?: number;
    active_workflows?: number;
  };
  payments?: Record<string, unknown>;
  escalations?: Record<string, unknown>;
  workflow_performance?: {
    workflows?: Array<{
      workflow_id: number;
      workflow_name?: string;
      run_count?: number;
      completed_count?: number;
      avg_duration_s?: number;
    }>;
  };
  business_call_analytics?: {
    total_calls?: number;
    rates?: Record<string, number | null>;
    kpis?: Record<string, {
      name: string;
      value?: number | null;
      rate?: number | null;
      count?: number;
    }>;
  };
}

export interface VoiceDashboardSummary {
  organization_id: number;
  from_ts: number;
  to_ts: number;
  generated_at: number;
  metrics: Record<string, unknown>;
  rates: Record<string, number | null>;
}

export async function fetchAdminSummary(days: AnalyticsDays = 7): Promise<AdminSummary> {
  const response = await client.get({
    url: '/api/v1/admin-operations/summary',
    query: { days },
  });
  if (response.error) {
    const detail =
      typeof response.error === 'object' && response.error !== null && 'detail' in response.error
        ? String((response.error as { detail?: unknown }).detail)
        : undefined;
    throw new Error(detail ?? 'Failed to load admin analytics summary');
  }
  return response.data as AdminSummary;
}

export async function fetchVoiceDashboard(
  organizationId: number,
  days: AnalyticsDays = 7,
): Promise<VoiceDashboardSummary> {
  const response = await client.get({
    url: '/api/v1/voice-analytics/dashboard',
    query: { organization_id: organizationId, days },
  });
  if (response.error) {
    throw new Error('Failed to load voice analytics dashboard');
  }
  return response.data as VoiceDashboardSummary;
}

export async function fetchBusinessMetrics(
  organizationId: number,
  days: AnalyticsDays = 7,
) {
  const response = await client.get({
    url: '/api/v1/business-call-analytics/metrics',
    query: { organization_id: organizationId, days },
  });
  if (response.error) {
    throw new Error('Failed to load business call metrics');
  }
  return response.data;
}
