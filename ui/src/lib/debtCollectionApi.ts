import { client } from '@/client/client.gen';

export interface DebtCollectionStatus {
  enabled: boolean;
  template_id: string;
  compliance: Record<string, unknown>;
}

export interface DebtSessionDetail {
  session_id: string;
  organization_id: number;
  workflow_run_id: number | null;
  vertical_instance_id: string;
  locale: string;
  negotiation_outcome: string;
  escalation_risk: string;
  negotiation_rounds: number;
  refusal_count: number;
  interruption_count: number;
  commitments: Array<Record<string, unknown>>;
  installment_plan: Record<string, unknown> | null;
  account: Record<string, unknown> | null;
}

export interface ComplianceCheckResult {
  allowed: boolean;
  violations: string[];
  sanitized_text?: string;
}

function extractError(response: { error?: unknown }, fallback: string): string {
  if (typeof response.error === 'object' && response.error !== null && 'detail' in response.error) {
    return String((response.error as { detail?: unknown }).detail);
  }
  return fallback;
}

export async function fetchDebtCollectionStatus(): Promise<DebtCollectionStatus> {
  const response = await client.get({ url: '/api/v1/debt-collection/status' });
  if (response.error) {
    return { enabled: false, template_id: '', compliance: {} };
  }
  return response.data as DebtCollectionStatus;
}

export async function getDebtSession(sessionId: string): Promise<DebtSessionDetail> {
  const response = await client.get({
    url: `/api/v1/debt-collection/sessions/${encodeURIComponent(sessionId)}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Session not found'));
  }
  return response.data as DebtSessionDetail;
}

export async function getComplianceAudit(sessionId: string) {
  const response = await client.get({
    url: `/api/v1/debt-collection/sessions/${encodeURIComponent(sessionId)}/compliance/audit`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Audit not found'));
  }
  return response.data as {
    session_id: string;
    entries: Array<Record<string, unknown>>;
    violation_count: number;
  };
}

export async function checkComplianceText(
  text: string,
  speaker: 'agent' | 'customer' = 'agent',
): Promise<ComplianceCheckResult> {
  const response = await client.post({
    url: '/api/v1/debt-collection/compliance/check',
    body: { text, speaker },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Compliance check failed'));
  }
  return response.data as ComplianceCheckResult;
}
