'use client';

import { format, parseISO } from 'date-fns';
import { Activity, GitBranch, Radio, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { OrchestrationsPanel } from '@/app/platform/components/OrchestrationsPanel';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useOrgConfig } from '@/context/OrgConfigContext';
import { useAuth } from '@/lib/auth';
import {
  type DeadLetterEntry,
  type DurableExecutionStatus,
  fetchDurableExecutionStatus,
  fetchPlatformEventsStatus,
  fetchPlatformObservability,
  listDeadLetterEvents,
  listPlatformEvents,
  type PlatformEvent,
  type PlatformEventStatus,
  type PlatformObservability,
  processPlatformEventRetries,
  publishPlatformEvent,
  replayPlatformEvent,
  replayPlatformEvents,
} from '@/lib/platformOpsApi';

function formatTs(value: string | null) {
  if (!value) return '—';
  try {
    return format(parseISO(value), 'MMM d, yyyy · h:mm a');
  } catch {
    return value;
  }
}

export default function PlatformOpsPage() {
  const auth = useAuth();
  const { orgContext } = useOrgConfig();
  const organizationId = orgContext?.organization_id ?? null;

  const [eventStatus, setEventStatus] = useState<PlatformEventStatus | null>(null);
  const [durableStatus, setDurableStatus] = useState<DurableExecutionStatus | null>(null);
  const [events, setEvents] = useState<PlatformEvent[]>([]);
  const [observability, setObservability] = useState<PlatformObservability | null>(null);
  const [deadLetter, setDeadLetter] = useState<DeadLetterEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [correlationFilter, setCorrelationFilter] = useState('');
  const [selectedEvent, setSelectedEvent] = useState<PlatformEvent | null>(null);
  const [replaying, setReplaying] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishType, setPublishType] = useState('workflow.completed');
  const [publishPayload, setPublishPayload] = useState('{}');
  const [publishing, setPublishing] = useState(false);

  const load = useCallback(async () => {
    if (!organizationId) return;

    setLoading(true);
    setError(null);

    try {
      const [platformStatus, orchestrationStatus] = await Promise.all([
        fetchPlatformEventsStatus(),
        fetchDurableExecutionStatus(),
      ]);
      setEventStatus(platformStatus);
      setDurableStatus(orchestrationStatus);

      if (platformStatus.enabled) {
        const [eventRows, obs, dlq] = await Promise.all([
          listPlatformEvents({
            organizationId,
            days: 7,
            eventType: eventTypeFilter || undefined,
            correlationId: correlationFilter || undefined,
          }),
          fetchPlatformObservability(organizationId),
          listDeadLetterEvents(organizationId),
        ]);
        setEvents(eventRows);
        setObservability(obs);
        setDeadLetter(dlq);
      } else {
        setEvents([]);
        setObservability(null);
        setDeadLetter([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load platform ops');
    } finally {
      setLoading(false);
    }
  }, [organizationId, eventTypeFilter, correlationFilter]);

  useEffect(() => {
    if (!auth.isAuthenticated) return;
    void load();
  }, [auth.isAuthenticated, load]);

  const handleProcessRetries = async () => {
    if (!organizationId) return;
    setRetrying(true);
    try {
      await processPlatformEventRetries(organizationId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to queue retries');
    } finally {
      setRetrying(false);
    }
  };

  const handleReplayAll = async () => {
    if (!organizationId) return;
    setReplaying(true);
    try {
      await replayPlatformEvents({
        organizationId,
        eventType: eventTypeFilter || undefined,
        days: 7,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Replay failed');
    } finally {
      setReplaying(false);
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    setError(null);
    try {
      const payload = JSON.parse(publishPayload) as Record<string, unknown>;
      await publishPlatformEvent({
        event_type: publishType,
        payload,
      });
      setPublishOpen(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Publish failed');
    } finally {
      setPublishing(false);
    }
  };

  if (!auth.isAuthenticated) {
    return null;
  }

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Platform operations</h1>
          <p className="text-sm text-muted-foreground">
            Event bus health, dead-letter queue, and durable orchestration status.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Radio className="h-4 w-4" />
              Platform event bus
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <Badge variant={eventStatus?.enabled ? 'default' : 'secondary'}>
                {eventStatus?.enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            )}
            {eventStatus?.registered_handlers?.length ? (
              <p className="mt-2 text-xs text-muted-foreground">
                {eventStatus.registered_handlers.length} handler types registered
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <GitBranch className="h-4 w-4" />
              Durable orchestration
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <Badge variant={durableStatus?.enabled ? 'default' : 'secondary'}>
                {durableStatus?.enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            )}
            {durableStatus?.definitions?.length ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {durableStatus.definitions.map((name) => (
                  <Badge key={name} variant="outline" className="text-xs">
                    {name}
                  </Badge>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {!organizationId ? (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            Select an organization to view platform events.
          </CardContent>
        </Card>
      ) : eventStatus?.enabled === false ? (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            Platform events are disabled. Set <code>PLATFORM_EVENTS_ENABLED=true</code> on the API.
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="events">
          <TabsList>
            <TabsTrigger value="events">Recent events</TabsTrigger>
            <TabsTrigger value="orchestrations">Orchestrations</TabsTrigger>
            <TabsTrigger value="observability">Observability</TabsTrigger>
            <TabsTrigger value="dlq">
              Dead letter
              {deadLetter.length > 0 ? ` (${deadLetter.length})` : ''}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="events" className="mt-4 space-y-4">
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                placeholder="Filter by event type…"
                value={eventTypeFilter}
                onChange={(e) => setEventTypeFilter(e.target.value)}
              />
              <Input
                placeholder="Filter by correlation ID…"
                value={correlationFilter}
                onChange={(e) => setCorrelationFilter(e.target.value)}
              />
              <Button variant="secondary" onClick={() => void load()}>
                Apply
              </Button>
              <Button variant="outline" onClick={() => void handleReplayAll()} disabled={replaying}>
                {replaying ? 'Replaying…' : 'Replay filtered'}
              </Button>
              <Button variant="outline" onClick={() => setPublishOpen(true)}>
                Publish test event
              </Button>
            </div>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Last 7 days</CardTitle>
                <CardDescription>Click a row for payload details.</CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <Skeleton className="h-40 w-full" />
                ) : events.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No platform events yet.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Time</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Source</TableHead>
                        <TableHead>Correlation</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {events.map((event) => (
                        <TableRow
                          key={event.event_id}
                          className="cursor-pointer"
                          onClick={() => setSelectedEvent(event)}
                        >
                          <TableCell className="whitespace-nowrap text-xs">
                            {formatTs(event.created_at)}
                          </TableCell>
                          <TableCell className="font-mono text-xs">{event.event_type}</TableCell>
                          <TableCell>{event.source}</TableCell>
                          <TableCell className="max-w-[200px] truncate text-xs text-muted-foreground">
                            {event.correlation_id ?? '—'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="orchestrations" className="mt-4">
            <OrchestrationsPanel enabled={durableStatus?.enabled ?? false} />
          </TabsContent>

          <TabsContent value="observability" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="h-4 w-4" />
                  Counters
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <Skeleton className="h-24 w-full" />
                ) : observability ? (
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {Object.entries(observability.counters).map(([key, value]) => (
                      <div key={key} className="rounded-lg border p-3">
                        <p className="text-xs text-muted-foreground">{key}</p>
                        <p className="text-2xl font-semibold">{value}</p>
                      </div>
                    ))}
                    {Object.keys(observability.counters).length === 0 ? (
                      <p className="text-sm text-muted-foreground">No counters recorded yet.</p>
                    ) : null}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="dlq" className="mt-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base">Dead letter queue</CardTitle>
                  <CardDescription>Events that failed routing or handler execution.</CardDescription>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => void handleProcessRetries()}
                  disabled={retrying || deadLetter.length === 0}
                >
                  {retrying ? 'Queueing…' : 'Process retries'}
                </Button>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <Skeleton className="h-24 w-full" />
                ) : deadLetter.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Dead letter queue is empty.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Event</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Reason</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {deadLetter.map((entry, index) => (
                        <TableRow key={String(entry.event_id ?? index)}>
                          <TableCell className="font-mono text-xs">
                            {String(entry.event_id ?? '—')}
                          </TableCell>
                          <TableCell>{String(entry.event_type ?? '—')}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {String(entry.reason ?? '—')}
                          </TableCell>
                          <TableCell>
                            {entry.event_id ? (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void replayPlatformEvent(String(entry.event_id)).then(() => load())}
                              >
                                Replay
                              </Button>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}

      <Sheet open={selectedEvent !== null} onOpenChange={(open) => !open && setSelectedEvent(null)}>
        <SheetContent className="overflow-y-auto sm:max-w-md">
          {selectedEvent ? (
            <>
              <SheetHeader>
                <SheetTitle>{selectedEvent.event_type}</SheetTitle>
                <SheetDescription>{selectedEvent.event_id}</SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-3 text-sm">
                <p>
                  <span className="font-medium">Source:</span> {selectedEvent.source}
                </p>
                <p>
                  <span className="font-medium">Correlation:</span>{' '}
                  {selectedEvent.correlation_id ?? '—'}
                </p>
                <pre className="max-h-80 overflow-auto rounded border bg-muted/40 p-3 text-xs">
                  {JSON.stringify(selectedEvent.payload, null, 2)}
                </pre>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    void replayPlatformEvent(selectedEvent.event_id).then(() => load())
                  }
                >
                  Replay event
                </Button>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>

      <Sheet open={publishOpen} onOpenChange={setPublishOpen}>
        <SheetContent className="sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Publish platform event</SheetTitle>
            <SheetDescription>Inject a typed event into the bus for testing.</SheetDescription>
          </SheetHeader>
          <div className="mt-4 space-y-3">
            <Input
              placeholder="event_type e.g. workflow.completed"
              value={publishType}
              onChange={(e) => setPublishType(e.target.value)}
            />
            <textarea
              className="min-h-[160px] w-full rounded-md border bg-background p-3 font-mono text-xs"
              value={publishPayload}
              onChange={(e) => setPublishPayload(e.target.value)}
            />
            <Button onClick={() => void handlePublish()} disabled={publishing}>
              {publishing ? 'Publishing…' : 'Publish'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
