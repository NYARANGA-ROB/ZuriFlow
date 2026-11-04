'use client';

import { format, parseISO } from 'date-fns';
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
import {
  getOrchestration,
  listOrchestrationEvents,
  listOrchestrations,
  type OrchestrationEvent,
  type OrchestrationSummary,
  resumeOrchestration,
} from '@/lib/platformOpsApi';

function formatTs(value: string | null) {
  if (!value) return '—';
  try {
    return format(parseISO(value), 'MMM d, yyyy · h:mm a');
  } catch {
    return value;
  }
}

export function OrchestrationsPanel({ enabled }: { enabled: boolean }) {
  const [rows, setRows] = useState<OrchestrationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Awaited<ReturnType<typeof getOrchestration>> | null>(null);
  const [events, setEvents] = useState<OrchestrationEvent[]>([]);
  const [resuming, setResuming] = useState(false);

  const load = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await listOrchestrations({ limit: 50 });
      setRows(data);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    void load();
  }, [load]);

  const openDetail = async (id: number) => {
    setSelectedId(id);
    try {
      const [orch, evs] = await Promise.all([
        getOrchestration(id),
        listOrchestrationEvents(id),
      ]);
      setDetail(orch);
      setEvents(evs);
    } catch {
      setDetail(null);
      setEvents([]);
    }
  };

  const handleResume = async () => {
    if (!selectedId) return;
    setResuming(true);
    try {
      const result = await resumeOrchestration(selectedId);
      setDetail(result);
      await load();
    } finally {
      setResuming(false);
    }
  };

  if (!enabled) {
    return (
      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground">
          Durable orchestration is disabled.
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Durable orchestrations</CardTitle>
          <CardDescription>Post-call WhatsApp, M-Pesa payment wait, and other sagas.</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-40 w-full" />
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No orchestrations yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Definition</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Step</TableHead>
                  <TableHead>Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow
                    key={row.id}
                    className="cursor-pointer"
                    onClick={() => void openDetail(row.id)}
                  >
                    <TableCell>#{row.id}</TableCell>
                    <TableCell className="font-mono text-xs">{row.definition_name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{row.status}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">{row.current_step}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatTs(row.updated_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Sheet open={selectedId !== null} onOpenChange={(open) => !open && setSelectedId(null)}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          {detail ? (
            <>
              <SheetHeader>
                <SheetTitle>Orchestration #{detail.orchestration_id}</SheetTitle>
                <SheetDescription>
                  {detail.definition_name} · {detail.orchestration_key}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge>{detail.status}</Badge>
                  <Badge variant="outline">Step: {detail.current_step}</Badge>
                </div>
                {detail.error_message ? (
                  <p className="text-sm text-destructive">{detail.error_message}</p>
                ) : null}
                <Button size="sm" onClick={() => void handleResume()} disabled={resuming}>
                  {resuming ? 'Resuming…' : 'Resume'}
                </Button>
                <div>
                  <p className="mb-2 text-sm font-medium">Event log</p>
                  <ul className="space-y-2 text-xs">
                    {events.map((event) => (
                      <li key={event.id} className="rounded border p-2">
                        <span className="font-medium">{event.event_type}</span>
                        <span className="text-muted-foreground"> · {formatTs(event.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-2 text-sm font-medium">State</p>
                  <pre className="max-h-48 overflow-auto rounded border bg-muted/40 p-2 text-xs">
                    {JSON.stringify(detail.state, null, 2)}
                  </pre>
                </div>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}
