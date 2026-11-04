'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
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
  claimEscalation,
  type EscalationDashboard,
  fetchEscalationDashboard,
  fetchEscalationStatus,
  getHandoff,
  type HandoffPackage,
  resolveEscalation,
  transferHandoff,
} from '@/lib/escalationApi';

export default function EscalationsPage() {
  const auth = useAuth();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [dashboard, setDashboard] = useState<EscalationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<HandoffPackage | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const status = await fetchEscalationStatus();
      setEnabled(status.enabled);
      if (!status.enabled) return;
      const data = await fetchEscalationDashboard();
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load escalations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!auth.isAuthenticated) return;
    void load();
  }, [auth.isAuthenticated, load]);

  const openHandoff = async (sessionId: string) => {
    try {
      const handoff = await getHandoff(sessionId);
      setSelected(handoff);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Handoff not found');
    }
  };

  const handleClaim = async () => {
    setActing(true);
    try {
      const claim = await claimEscalation();
      if (claim?.handoff) {
        setSelected(claim.handoff);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Claim failed');
    } finally {
      setActing(false);
    }
  };

  const handleResolve = async () => {
    if (!selected) return;
    setActing(true);
    try {
      await resolveEscalation(selected.session_id);
      setSelected(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Resolve failed');
    } finally {
      setActing(false);
    }
  };

  const handleTransfer = async () => {
    if (!selected) return;
    setActing(true);
    try {
      await transferHandoff(selected.session_id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transfer failed');
    } finally {
      setActing(false);
    }
  };

  if (!auth.isAuthenticated) return null;

  if (enabled === false) {
    return (
      <div className="container max-w-5xl py-8">
        <Card>
          <CardHeader>
            <CardTitle>Human escalations</CardTitle>
            <CardDescription>
              Disabled. Set <code>HUMAN_ESCALATION_ENABLED=true</code> on the API.
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
          <h1 className="text-2xl font-semibold tracking-tight">Human escalations</h1>
          <p className="text-sm text-muted-foreground">
            Operator queue for live handoffs from voice agents.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            Refresh
          </Button>
          <Button onClick={() => void handleClaim()} disabled={acting}>
            Claim next
          </Button>
        </div>
      </div>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : dashboard ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Pending</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{dashboard.pending_count}</p>
              </CardContent>
            </Card>
            {Object.entries(dashboard.queue_depths).map(([queue, depth]) => (
              <Card key={queue}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Queue: {queue}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{depth}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pending handoffs</CardTitle>
            </CardHeader>
            <CardContent>
              {dashboard.pending.length === 0 ? (
                <p className="text-sm text-muted-foreground">No pending escalations.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Customer</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Risk</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dashboard.pending.map((item) => (
                      <TableRow
                        key={item.session_id}
                        className="cursor-pointer"
                        onClick={() => void openHandoff(item.session_id)}
                      >
                        <TableCell>
                          {item.handoff.customer_name || item.handoff.phone_e164 || '—'}
                        </TableCell>
                        <TableCell className="max-w-[240px] truncate">
                          {item.handoff.reason}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.handoff.risk_level}</Badge>
                        </TableCell>
                        <TableCell>{item.handoff.priority}</TableCell>
                        <TableCell>{item.claimed ? 'Claimed' : 'Waiting'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}

      <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          {selected ? (
            <>
              <SheetHeader>
                <SheetTitle>{selected.customer_name || 'Handoff'}</SheetTitle>
                <SheetDescription>{selected.session_id}</SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-4 text-sm">
                <p>
                  <span className="font-medium">Phone:</span> {selected.phone_e164 || '—'}
                </p>
                <p>
                  <span className="font-medium">Reason:</span> {selected.reason}
                </p>
                <p className="whitespace-pre-wrap text-muted-foreground">{selected.summary}</p>
                {selected.workflow_run_id ? (
                  <Link
                    href={`/usage?run=${selected.workflow_run_id}`}
                    className="text-primary hover:underline"
                  >
                    View workflow run #{selected.workflow_run_id}
                  </Link>
                ) : null}
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => void handleTransfer()} disabled={acting}>
                    Transfer
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void handleResolve()}
                    disabled={acting}
                  >
                    Resolve
                  </Button>
                </div>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
