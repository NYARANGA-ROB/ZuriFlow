'use client';

import { MessageSquare, Phone, Receipt, Reply, Smartphone } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/lib/auth';
import {
  type EngagementDashboard,
  fetchEngagementDashboard,
  fetchEngagementStatus,
} from '@/lib/omnichannelApi';

function pct(value: number): string {
  return `${Math.round((value || 0) * 1000) / 10}%`;
}

export default function EngagementPage() {
  const auth = useAuth();
  const [days, setDays] = useState(30);
  const [data, setData] = useState<EngagementDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const status = await fetchEngagementStatus();
      if (!status.enabled) {
        setError('Omnichannel engagement is turned off for this workspace.');
        setData(null);
        return;
      }
      setData(await fetchEngagementDashboard(days));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load engagement');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    if (!auth.isAuthenticated) return;
    void load();
  }, [auth.isAuthenticated, load]);

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Customer engagement</h1>
          <p className="text-muted-foreground mt-1">
            One conversation across voice, SMS, WhatsApp, and web chat — including M-Pesa
            receipts.
          </p>
        </div>
        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric title="Messages sent" value={data.messages_sent} icon={MessageSquare} />
            <Metric title="Delivery rate" value={pct(data.delivery_rate)} icon={Smartphone} />
            <Metric title="Response rate" value={pct(data.response_rate)} icon={Reply} />
            <Metric
              title="Voice → WhatsApp"
              value={pct(data.channel_conversion.voice_to_whatsapp_rate)}
              hint={`${data.channel_conversion.voice_to_whatsapp} conversations`}
              icon={Phone}
            />
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Payment conversion</CardTitle>
              <CardDescription>
                Conversations that included an M-Pesa receipt or payment on the same thread.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex items-center gap-3">
              <Receipt className="h-5 w-5 text-muted-foreground" />
              <div>
                <div className="text-2xl font-bold">
                  {pct(data.channel_conversion.payment_conversion_rate)}
                </div>
                <p className="text-sm text-muted-foreground">
                  {data.channel_conversion.payment_conversions} of{' '}
                  {data.channel_conversion.conversations} conversations
                </p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>By channel</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(data.by_channel || []).length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No omnichannel messages yet. Missed-call SMS, payment receipts, and WhatsApp
                  follow-ups will appear here on the same customer timeline.
                </p>
              )}
              {data.by_channel.map((row) => (
                <div
                  key={row.channel}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm"
                >
                  <span className="font-medium capitalize">{row.channel.replace('_', ' ')}</span>
                  <span>
                    {row.messages_sent} sent · {pct(row.delivery_rate)} delivered ·{' '}
                    {pct(row.response_rate)} replied
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function Metric({
  title,
  value,
  hint,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  hint?: string;
  icon: typeof Phone;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
