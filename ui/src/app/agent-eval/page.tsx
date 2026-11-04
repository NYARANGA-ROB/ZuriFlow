'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuth } from '@/lib/auth';
import {
  type AgentEvalResult,
  type AgentEvalRun,
  type AgentEvalScenario,
  type AgentEvalStatus,
  fetchEvalRun,
  fetchEvalRuns,
  fetchEvalStatus,
  fetchScenarios,
  rerunFailed,
  rerunScenario,
  runEvalSuite,
} from '@/lib/agentEvalApi';

const PILLARS = [
  'accuracy',
  'safety',
  'latency',
  'completion',
  'customer_experience',
] as const;

export default function AgentEvalPage() {
  const { user, loading: authLoading } = useAuth();
  const hasFetched = useRef(false);
  const [status, setStatus] = useState<AgentEvalStatus | null>(null);
  const [scenarios, setScenarios] = useState<AgentEvalScenario[]>([]);
  const [runs, setRuns] = useState<AgentEvalRun[]>([]);
  const [selected, setSelected] = useState<AgentEvalResult | null>(null);
  const [activeRun, setActiveRun] = useState<{
    run: AgentEvalRun;
    results: AgentEvalResult[];
    score: AgentEvalRun['score'];
    comparison: AgentEvalRun['comparison'];
  } | null>(null);
  const [workflowId, setWorkflowId] = useState('');
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const st = await fetchEvalStatus();
      setStatus(st);
      if (!st.enabled) return;
      const [sc, rs] = await Promise.all([fetchScenarios(), fetchEvalRuns()]);
      setScenarios(sc);
      setRuns(rs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load evaluation data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !user || hasFetched.current) return;
    hasFetched.current = true;
    void load();
  }, [authLoading, user, load]);

  const handleRun = async () => {
    setBusy(true);
    setError(null);
    try {
      const wf = workflowId ? Number(workflowId) : undefined;
      const data = await runEvalSuite(Number.isFinite(wf) ? wf : undefined);
      setActiveRun(data);
      setRuns((prev) => [data.run, ...prev]);
      setSelected(data.results[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Suite failed');
    } finally {
      setBusy(false);
    }
  };

  const handleOpenRun = async (runId: number) => {
    setBusy(true);
    try {
      const data = await fetchEvalRun(runId);
      setActiveRun(data);
      setSelected(data.results[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open run');
    } finally {
      setBusy(false);
    }
  };

  const handleRerunFailed = async () => {
    if (!activeRun) return;
    setBusy(true);
    try {
      const data = (await rerunFailed(activeRun.run.id)) as typeof activeRun;
      setActiveRun(data);
      setSelected(data.results.find((r) => !r.passed) ?? data.results[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rerun failed');
    } finally {
      setBusy(false);
    }
  };

  const handleRerunOne = async (scenarioId: string) => {
    setBusy(true);
    try {
      const wf = workflowId ? Number(workflowId) : activeRun?.run.workflow_id ?? undefined;
      const data = (await rerunScenario(scenarioId, wf ?? undefined)) as typeof activeRun;
      setActiveRun(data);
      setSelected(data.results[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scenario rerun failed');
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !user) return null;

  if (status && !status.enabled) {
    return (
      <div className="container max-w-5xl py-8">
        <Card>
          <CardHeader>
            <CardTitle>Agent evaluation</CardTitle>
            <CardDescription>
              Disabled. Set <code>AGENT_EVAL_ENABLED=true</code> on the API.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const visibleScenarios =
    filter === 'all' ? scenarios : scenarios.filter((s) => s.category === filter);

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Agent evaluation</h1>
        <p className="text-sm text-muted-foreground">
          Synthetic conversations for workflow, prompt, language, and tool regressions.
          Scores are engineering metrics, not SLAs.
        </p>
      </div>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {status ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Training policy</CardTitle>
            <CardDescription>{status.training_policy}</CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run agent suite</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Input
            placeholder="Workflow ID (optional)"
            value={workflowId}
            onChange={(e) => setWorkflowId(e.target.value)}
          />
          <Button onClick={() => void handleRun()} disabled={busy}>
            {busy ? 'Running…' : 'Run suite'}
          </Button>
          {activeRun ? (
            <Button variant="outline" onClick={() => void handleRerunFailed()} disabled={busy}>
              Rerun failed
            </Button>
          ) : null}
        </CardContent>
      </Card>

      {loading ? <Skeleton className="h-40 w-full" /> : null}

      {activeRun ? (
        <>
          <div className="grid gap-3 sm:grid-cols-5">
            {PILLARS.map((pillar) => (
              <Card key={pillar}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs capitalize">{pillar.replaceAll('_', ' ')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-semibold">
                    {(activeRun.score.pillars[pillar] ?? 0).toFixed(1)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
          <p className="text-sm text-muted-foreground">
            Overall {activeRun.score.overall.toFixed(1)} — pass rate{' '}
            {((activeRun.score.metrics.pass_rate ?? 0) * 100).toFixed(0)}% (
            {activeRun.score.metrics.passed}/{activeRun.score.metrics.total}). Underlying metrics:{' '}
            intent {activeRun.score.metrics.intent_accuracy}, tools{' '}
            {activeRun.score.metrics.tool_call_accuracy}, hallucination{' '}
            {activeRun.score.metrics.hallucination_rate}, payment safety{' '}
            {activeRun.score.metrics.payment_safety}, latency p50{' '}
            {activeRun.score.metrics.response_latency_ms_p50}ms.
          </p>
          {activeRun.comparison.has_baseline ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Previous version vs new version</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 sm:grid-cols-5">
                {PILLARS.map((pillar) => {
                  const delta = activeRun.comparison.deltas?.[pillar];
                  return (
                    <div key={pillar} className="rounded-lg border p-3 text-sm">
                      <p className="capitalize text-muted-foreground">{pillar.replaceAll('_', ' ')}</p>
                      <p>
                        {delta?.previous.toFixed(1)} → {delta?.new.toFixed(1)}
                      </p>
                      <p className={delta && delta.delta < 0 ? 'text-destructive' : 'text-muted-foreground'}>
                        {delta && delta.delta >= 0 ? '+' : ''}
                        {delta?.delta.toFixed(1)}
                      </p>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          ) : (
            <p className="text-sm text-muted-foreground">
              No previous published version to compare yet.
            </p>
          )}
        </>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Scenarios</CardTitle>
            <Select value={filter} onValueChange={setFilter}>
              <SelectTrigger className="w-[200px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {(status?.categories ?? []).map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent className="max-h-[480px] overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scenario</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleScenarios.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell>
                      <p className="font-medium">{s.title}</p>
                      <p className="text-xs text-muted-foreground">{s.id}</p>
                    </TableCell>
                    <TableCell className="text-xs">{s.category}</TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() => void handleRerunOne(s.id)}
                      >
                        Run
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {selected ? selected.title : 'Scenario detail'}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {!selected ? (
              <p className="text-muted-foreground">Run a suite or a scenario to inspect a transcript.</p>
            ) : (
              <>
                <Badge variant={selected.passed ? 'default' : 'destructive'}>
                  {selected.passed ? 'Pass' : 'Fail'}
                </Badge>
                <section>
                  <h3 className="font-medium">Transcript</h3>
                  <div className="mt-1 space-y-1">
                    {selected.transcript.map((turn, i) => (
                      <p key={i}>
                        <span className="text-muted-foreground">{turn.role}: </span>
                        {turn.text}
                      </p>
                    ))}
                  </div>
                </section>
                <section>
                  <h3 className="font-medium">Tool calls</h3>
                  <p className="text-muted-foreground">
                    {selected.tool_calls.length
                      ? selected.tool_calls.map((t) => t.name).join(', ')
                      : 'None'}
                  </p>
                </section>
                <section>
                  <h3 className="font-medium">Workflow path</h3>
                  <p className="text-muted-foreground">
                    {selected.workflow_path.length ? selected.workflow_path.join(' → ') : '—'}
                  </p>
                </section>
                <section>
                  <h3 className="font-medium">Expected vs actual</h3>
                  <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted p-2 text-xs">
                    {JSON.stringify(
                      { expected: selected.expected, actual: selected.actual },
                      null,
                      2,
                    )}
                  </pre>
                </section>
                <section>
                  <h3 className="font-medium">Evaluation checks</h3>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {Object.entries(selected.evaluation.checks).map(([key, ok]) => (
                      <Badge key={key} variant={ok ? 'outline' : 'destructive'} className="text-xs">
                        {key}: {ok ? 'pass' : 'fail'}
                      </Badge>
                    ))}
                  </div>
                </section>
                {!selected.passed ? (
                  <Button size="sm" onClick={() => void handleRerunOne(selected.scenario_id)}>
                    Rerun this scenario
                  </Button>
                ) : null}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {activeRun ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Suite results</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scenario</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead>Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeRun.results.map((row) => (
                  <TableRow
                    key={row.scenario_id}
                    className="cursor-pointer"
                    onClick={() => setSelected(row)}
                  >
                    <TableCell>{row.title}</TableCell>
                    <TableCell>{row.passed ? 'Pass' : 'Fail'}</TableCell>
                    <TableCell>{row.latency_ms != null ? `${row.latency_ms.toFixed(0)}ms` : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Previous runs</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No evaluation runs yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Trigger</TableHead>
                  <TableHead>Overall</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>#{run.id}</TableCell>
                    <TableCell>{run.trigger}</TableCell>
                    <TableCell>{run.score?.overall?.toFixed?.(1) ?? '—'}</TableCell>
                    <TableCell>
                      <Button size="sm" variant="ghost" onClick={() => void handleOpenRun(run.id)}>
                        Open
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
