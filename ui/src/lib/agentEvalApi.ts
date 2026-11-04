import { client } from '@/client/client.gen';
import { detailFromError } from '@/lib/apiError';

export interface AgentEvalStatus {
  enabled: boolean;
  scenario_count: number;
  categories: string[];
  pillars: string[];
  training_policy: string;
}

export interface AgentEvalScenario {
  id: string;
  category: string;
  title: string;
  user_turns: string[];
  expected: Record<string, unknown>;
  notes: string;
}

export interface AgentEvalResult {
  id: number;
  run_id: number;
  scenario_id: string;
  title: string;
  category: string;
  passed: boolean;
  expected: Record<string, unknown>;
  actual: Record<string, unknown>;
  evaluation: {
    passed: boolean;
    checks: Record<string, boolean>;
    metrics: Record<string, number>;
  };
  transcript: Array<{ role: string; text: string }>;
  tool_calls: Array<{ name: string; arguments?: Record<string, unknown> }>;
  workflow_path: string[];
  latency_ms: number | null;
}

export interface AgentEvalRun {
  id: number;
  workflow_id: number | null;
  workflow_definition_id: number | null;
  trigger: string;
  status: string;
  score: {
    overall: number;
    pillars: Record<string, number>;
    metrics: Record<string, number>;
    note?: string;
  };
  comparison: {
    has_baseline: boolean;
    deltas?: Record<string, { previous: number; new: number; delta: number }>;
    regressed_pillars?: string[];
  };
  created_at: string | null;
}

function unwrap<T>(response: { data?: T; error?: unknown }, fallback: string): T {
  if (response.error) {
    throw new Error(detailFromError(response.error, fallback));
  }
  return response.data as T;
}

export async function fetchEvalStatus(): Promise<AgentEvalStatus> {
  const response = await client.get({ url: '/api/v1/agent-eval/status' });
  if (response.error) {
    return {
      enabled: false,
      scenario_count: 0,
      categories: [],
      pillars: [],
      training_policy: '',
    };
  }
  return response.data as AgentEvalStatus;
}

export async function fetchScenarios(): Promise<AgentEvalScenario[]> {
  const response = await client.get({ url: '/api/v1/agent-eval/scenarios' });
  const data = unwrap<{ scenarios: AgentEvalScenario[] }>(response, 'Failed to load scenarios');
  return data.scenarios;
}

export async function fetchEvalRuns(workflowId?: number): Promise<AgentEvalRun[]> {
  const response = await client.get({
    url: '/api/v1/agent-eval/runs',
    query: workflowId ? { workflow_id: workflowId } : {},
  });
  const data = unwrap<{ runs: AgentEvalRun[] }>(response, 'Failed to load eval runs');
  return data.runs;
}

export async function fetchEvalRun(runId: number): Promise<{
  run: AgentEvalRun;
  results: AgentEvalResult[];
  score: AgentEvalRun['score'];
  comparison: AgentEvalRun['comparison'];
}> {
  const response = await client.get({ url: `/api/v1/agent-eval/runs/${runId}` });
  return unwrap(response, 'Failed to load eval run');
}

export async function runEvalSuite(workflowId?: number, scenarioIds?: string[]) {
  const response = await client.post({
    url: '/api/v1/agent-eval/runs',
    body: {
      workflow_id: workflowId ?? null,
      scenario_ids: scenarioIds ?? null,
    },
  });
  return unwrap<{
    run: AgentEvalRun;
    results: AgentEvalResult[];
    score: AgentEvalRun['score'];
    comparison: AgentEvalRun['comparison'];
  }>(response, 'Failed to run evaluation suite');
}

export async function rerunFailed(runId: number) {
  const response = await client.post({ url: `/api/v1/agent-eval/runs/${runId}/rerun-failed` });
  return unwrap(response, 'Failed to rerun failed scenarios');
}

export async function rerunScenario(scenarioId: string, workflowId?: number) {
  const response = await client.post({
    url: `/api/v1/agent-eval/scenarios/${scenarioId}/rerun`,
    body: { workflow_id: workflowId ?? null },
  });
  return unwrap(response, 'Failed to rerun scenario');
}
