'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useOrgConfig } from '@/context/OrgConfigContext';
import { useAuth } from '@/lib/auth';
import {
  type FailureSummary,
  fetchFailureSummary,
  fetchReliabilityStatus,
  listReliabilityDlq,
  listRetryQueue,
  processRetryQueue,
  type ReliabilityStatus,
  replaySession,
  replayWorkflowRun,
} from '@/lib/callReliabilityApi';

export default function ReliabilityPage() {
  const auth = useAuth();
  const { orgContext } = useOrgConfig();
  const organizationId = orgContext?.organization_id ?? null;

  const [status, setStatus] = useState<ReliabilityStatus | null>(null);
  const [summary, setSummary] = useState<FailureSummary | null>(null);
  const [retryQueue, setRetryQueue] = useState<Array<Record<string, unknown>>>([]);
  const [dlq, setDlq] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionReplay, setSessionReplay] = useState('');
  const [runReplay, setRunReplay] = useState('');

  const load = useCallback(async () => {
    if (!organizationId) return;
    setLoading(true);
    setError(null);
    try {
      const reliabilityStatus = await fetchReliabilityStatus();
      setStatus(reliabilityStatus);
      if (!reliabilityStatus.enabled) return;

      const [failureSummary, retries, deadLetter] = await Promise.all([
        fetchFailureSummary(organizationId, 7),
        listRetryQueue(organizationId),
        listReliabilityDlq(organizationId),
      ]);
      setSummary(failureSummary);
      setRetryQueue(retries);
      setDlq(deadLetter);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reliability data');
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    if (!auth.isAuthenticated) return;
    void load();
  }, [auth.isAuthenticated, load]);

  if (!auth.isAuthenticated) return null;

  if (status?.enabled === false) {
    return (
      <div className="container max-w-5xl py-8">
        <Card>
          <CardHeader>
            <CardTitle>Call reliability</CardTitle>
            <CardDescription>
              Disabled. Set <code>CALL_RELIABILITY_ENABLED=true</code> on the API.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Call reliability</h1>
          <p className="text-sm text-muted-foreground">
            Failure tracking, retry queue, and event replay for voice sessions.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          Refresh
        </Button>
      </div>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {!organizationId ? (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            Select an organization to view reliability metrics.
          </CardContent>
        </Card>
      ) : loading ? (
        <Skeleton className="h-48 w-full" />
      ) : (
        <>
          {summary ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(summary.totals).map(([key, value]) => (
                <Card key={key}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">{key}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold">{value}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Replay tools</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 sm:flex-row">
              <Input
                placeholder="Session ID"
                value={sessionReplay}
                onChange={(e) => setSessionReplay(e.target.value)}
              />
              <Button
                variant="secondary"
                onClick={() =>
                  sessionReplay.trim() &&
                  void replaySession(sessionReplay.trim()).then(() => load())
                }
              >
                Replay session
              </Button>
              <Input
                placeholder="Workflow run ID"
                value={runReplay}
                onChange={(e) => setRunReplay(e.target.value)}
              />
              <Button
                variant="secondary"
                onClick={() =>
                  runReplay.trim() &&
                  void replayWorkflowRun(Number(runReplay)).then(() => load())
                }
              >
                Replay run
              </Button>
            </CardContent>
          </Card>

          <Tabs defaultValue="retries">
            <TabsList>
              <TabsTrigger value="retries">Retry queue ({retryQueue.length})</TabsTrigger>
              <TabsTrigger value="dlq">Dead letter ({dlq.length})</TabsTrigger>
              <TabsTrigger value="recent">Recent failures</TabsTrigger>
            </TabsList>

            <TabsContent value="retries" className="mt-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-base">Pending retries</CardTitle>
                  <Button
                    size="sm"
                    onClick={() => void processRetryQueue(organizationId).then(() => load())}
                  >
                    Process queue
                  </Button>
                </CardHeader>
                <CardContent>
                  {retryQueue.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Retry queue is empty.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Session</TableHead>
                          <TableHead>Reason</TableHead>
                          <TableHead>Attempts</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {retryQueue.map((row, i) => (
                          <TableRow key={String(row.session_id ?? i)}>
                            <TableCell className="font-mono text-xs">
                              {String(row.session_id ?? '—')}
                            </TableCell>
                            <TableCell>{String(row.reason ?? '—')}</TableCell>
                            <TableCell>{String(row.attempt ?? '—')}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="dlq" className="mt-4">
              <Card>
                <CardContent className="pt-6">
                  {dlq.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Dead letter queue is empty.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Session</TableHead>
                          <TableHead>Reason</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {dlq.map((row, i) => (
                          <TableRow key={String(row.session_id ?? i)}>
                            <TableCell className="font-mono text-xs">
                              {String(row.session_id ?? '—')}
                            </TableCell>
                            <TableCell>{String(row.reason ?? '—')}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="recent" className="mt-4">
              <Card>
                <CardContent className="pt-6">
                  {(summary?.recent_failures ?? []).length === 0 ? (
                    <p className="text-sm text-muted-foreground">No recent failures.</p>
                  ) : (
                    <ul className="space-y-2 text-sm">
                      {summary?.recent_failures.map((f, i) => (
                        <li key={i} className="flex items-center justify-between gap-2 border-b pb-2">
                          <span className="font-mono text-xs">{String(f.session_id ?? '—')}</span>
                          <Badge variant="outline">{String(f.reason ?? 'failure')}</Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
