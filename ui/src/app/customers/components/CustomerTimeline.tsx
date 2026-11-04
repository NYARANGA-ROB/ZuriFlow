'use client';

import { format, parseISO } from 'date-fns';
import {
  CreditCard,
  GitBranch,
  type LucideIcon,
  Mail,
  Megaphone,
  MessageCircle,
  Phone,
  Settings,
  UserRound,
} from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  CHANNEL_LABELS,
  type TimelineEntry,
} from '@/lib/customerTimelineApi';

const CHANNEL_ICONS: Record<string, LucideIcon> = {
  voice: Phone,
  whatsapp: MessageCircle,
  email: Mail,
  payment: CreditCard,
  campaign: Megaphone,
  escalation: UserRound,
  orchestration: GitBranch,
  system: Settings,
};

function ChannelIcon({ channel }: { channel: string }) {
  const Icon = CHANNEL_ICONS[channel] ?? GitBranch;
  return <Icon className="h-4 w-4" />;
}

function TimelineRow({
  entry,
  onSelect,
}: {
  entry: TimelineEntry;
  onSelect: (entry: TimelineEntry) => void;
}) {
  const occurred = entry.occurred_at
    ? format(parseISO(entry.occurred_at), 'MMM d, yyyy · h:mm a')
    : '—';

  return (
    <button
      type="button"
      onClick={() => onSelect(entry)}
      className="relative flex w-full gap-4 pb-8 text-left last:pb-0 hover:opacity-90"
    >
      <div className="flex flex-col items-center">
        <div className="flex h-9 w-9 items-center justify-center rounded-full border bg-background shadow-sm">
          <ChannelIcon channel={entry.channel} />
        </div>
        <div className="mt-2 w-px flex-1 bg-border" />
      </div>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{entry.title}</span>
          <Badge variant="secondary" className="text-xs">
            {CHANNEL_LABELS[entry.channel] ?? entry.channel}
          </Badge>
        </div>
        {entry.summary ? (
          <p className="mt-1 text-sm text-muted-foreground">{entry.summary}</p>
        ) : null}
        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>{occurred}</span>
          {entry.workflow_run_id ? (
            <Link
              href={`/usage?run=${entry.workflow_run_id}`}
              className="text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              Run #{entry.workflow_run_id}
            </Link>
          ) : null}
          {entry.transaction_id ? (
            <span>M-Pesa txn #{entry.transaction_id}</span>
          ) : null}
        </div>
      </div>
    </button>
  );
}

export function CustomerTimelinePanel({
  entries,
  channelsActive,
}: {
  entries: TimelineEntry[];
  channelsActive: string[];
}) {
  const [selected, setSelected] = useState<TimelineEntry | null>(null);

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="text-base">Omnichannel timeline</CardTitle>
            {channelsActive.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {channelsActive.map((channel) => (
                  <Badge key={channel} variant="outline" className="text-xs">
                    {CHANNEL_LABELS[channel] ?? channel}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
        </CardHeader>
        <CardContent>
          {entries.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No cross-channel activity yet. Events appear here after voice calls, WhatsApp,
              email, M-Pesa payments, and campaigns.
            </p>
          ) : (
            <div className="pl-1">
              {entries.map((entry) => (
                <TimelineRow key={entry.id} entry={entry} onSelect={setSelected} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent className="overflow-y-auto sm:max-w-md">
          {selected ? (
            <>
              <SheetHeader>
                <SheetTitle>{selected.title}</SheetTitle>
                <SheetDescription>
                  {CHANNEL_LABELS[selected.channel] ?? selected.channel} · {selected.event_type}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-4 text-sm">
                {selected.summary ? (
                  <div>
                    <p className="font-medium">Summary</p>
                    <p className="text-muted-foreground">{selected.summary}</p>
                  </div>
                ) : null}
                <div>
                  <p className="font-medium">Occurred</p>
                  <p className="text-muted-foreground">
                    {selected.occurred_at
                      ? format(parseISO(selected.occurred_at), 'PPpp')
                      : '—'}
                  </p>
                </div>
                {selected.correlation_id ? (
                  <div>
                    <p className="font-medium">Correlation</p>
                    <p className="break-all font-mono text-xs text-muted-foreground">
                      {selected.correlation_id}
                    </p>
                  </div>
                ) : null}
                <div>
                  <p className="mb-2 font-medium">Payload</p>
                  <pre className="max-h-64 overflow-auto rounded-lg border bg-muted/40 p-3 text-xs">
                    {JSON.stringify(selected.payload, null, 2)}
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
