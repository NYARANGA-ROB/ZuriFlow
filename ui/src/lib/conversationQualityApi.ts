import { client } from '@/client/client.gen';

export interface QualityStatus {
  enabled: boolean;
  model_version: string;
  dimensions: string[];
}

export interface QualitySummary {
  organization_id: number;
  evaluation_count: number;
  avg_overall_score: number | null;
  dimension_averages: Record<string, number>;
  regression_count: number;
  recent_regressions: Array<Record<string, unknown>>;
}

export interface ConversationEvaluation {
  organization_id: number;
  workflow_run_id: number;
  workflow_id: number | null;
  model_version: string;
  overall_score: number;
  dimensions: Record<string, {
    dimension: string;
    score: number;
    weight: number;
    evidence: Record<string, unknown>;
    flags: string[];
  }>;
  metrics: Record<string, unknown>;
  regression: Record<string, unknown>;
  flags: string[];
  evaluated_at: string | null;
}

function extractError(response: { error?: unknown }, fallback: string): string {
  if (typeof response.error === 'object' && response.error !== null && 'detail' in response.error) {
    return String((response.error as { detail?: unknown }).detail);
  }
  return fallback;
}

export async function fetchQualityStatus(): Promise<QualityStatus> {
  const response = await client.get({ url: '/api/v1/conversation-quality/status' });
  if (response.error) {
    return { enabled: false, model_version: '', dimensions: [] };
  }
  return response.data as QualityStatus;
}

export async function fetchQualitySummary(days = 30): Promise<QualitySummary> {
  const response = await client.get({
    url: '/api/v1/conversation-quality/summary',
    query: { days },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load quality summary'));
  }
  return response.data as QualitySummary;
}

export async function listRegressions(days = 30, limit = 50) {
  const response = await client.get({
    url: '/api/v1/conversation-quality/regressions',
    query: { days, limit },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load regressions'));
  }
  return response.data as { evaluations: Array<Record<string, unknown>> };
}

export async function evaluateRun(workflowRunId: number): Promise<ConversationEvaluation> {
  const response = await client.post({
    url: `/api/v1/conversation-quality/evaluate/${workflowRunId}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Evaluation failed'));
  }
  return response.data as ConversationEvaluation;
}

export async function getRunEvaluation(workflowRunId: number): Promise<ConversationEvaluation> {
  const response = await client.get({
    url: `/api/v1/conversation-quality/runs/${workflowRunId}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Evaluation not found'));
  }
  return response.data as ConversationEvaluation;
}
