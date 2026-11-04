'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
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
  type ConversationEvaluation,
  evaluateRun,
  fetchQualityStatus,
  fetchQualitySummary,
  getRunEvaluation,
  listRegressions,
  type QualitySummary,
} from '@/lib/conversationQualityApi';

export default function ConversationQualityPage() {
  const auth = useAuth();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [days, setDays] = useState('30');
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [regressions, setRegressions] = useState<Array<Record<string, unknown>>>([]);
  const [runId, setRunId] = useState('');
  const [evaluation, setEvaluation] = useState<ConversationEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const status = await fetchQualityStatus();
      setEnabled(status.enabled);
      if (!status.enabled) return;

      const windowDays = Number(days);
      const [sum, reg] = await Promise.all([
        fetchQualitySummary(windowDays),
        listRegressions(windowDays),
      ]);
      setSummary(sum);
      setRegressions(reg.evaluations ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load quality data');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    if (!auth.isAuthenticated) return;
    void load();
  }, [auth.isAuthenticated, load]);

  const handleEvaluate = async () => {
    const id = Number(runId);
    if (!Number.isFinite(id)) return;
    setEvaluating(true);
    setError(null);
    try {
      const result = await evaluateRun(id);
      setEvaluation(result);
    } catch (err) {
      try {
        const existing = await getRunEvaluation(id);
        setEvaluation(existing);
      } catch {
        setError(err instanceof Error ? err.message : 'Evaluation failed');
      }
    } finally {
      setEvaluating(false);
    }
  };

  if (!auth.isAuthenticated) return null;

  if (enabled === false) {
    return (
      <div className="container max-w-5xl py-8">
        <Card>
          <CardHeader>
            <CardTitle>Conversation quality</CardTitle>
            <CardDescription>
              Disabled. Set <code>CONVERSATION_QUALITY_ENABLED=true</code> on the API.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Conversation quality</h1>
          <p className="text-sm text-muted-foreground">
            Automated scoring and regression detection for agent runs.
          </p>
        </div>
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : summary ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Evaluations</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{summary.evaluation_count}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Avg score</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {summary.avg_overall_score != null
                  ? summary.avg_overall_score.toFixed(2)
                  : '—'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Regressions</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{summary.regression_count}</p>
            </CardContent>
          </Card>
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Evaluate a run</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Input
            placeholder="Workflow run ID"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
          />
          <Button onClick={() => void handleEvaluate()} disabled={evaluating}>
            {evaluating ? 'Evaluating…' : 'Evaluate'}
          </Button>
        </CardContent>
      </Card>

      {evaluation ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Run #{evaluation.workflow_run_id} — score {evaluation.overall_score.toFixed(2)}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {Object.entries(evaluation.dimensions).map(([key, dim]) => (
              <div key={key} className="rounded-lg border p-3">
                <p className="text-sm font-medium">{dim.dimension}</p>
                <p className="text-2xl font-semibold">{dim.score.toFixed(2)}</p>
                {dim.flags.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {dim.flags.map((flag) => (
                      <Badge key={flag} variant="outline" className="text-xs">
                        {flag}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
            <Link
              href={`/usage?run=${evaluation.workflow_run_id}`}
              className="text-sm text-primary hover:underline"
            >
              Open agent run
            </Link>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Regressions</CardTitle>
        </CardHeader>
        <CardContent>
          {regressions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No regressions in this window.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Flags</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {regressions.map((row, i) => (
                  <TableRow key={String(row.workflow_run_id ?? i)}>
                    <TableCell>#{String(row.workflow_run_id ?? '—')}</TableCell>
                    <TableCell>{String(row.overall_score ?? '—')}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {Array.isArray(row.flags) ? row.flags.join(', ') : '—'}
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
