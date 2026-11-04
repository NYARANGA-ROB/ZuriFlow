'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useOrgConfig } from '@/context/OrgConfigContext';
import { useAuth } from '@/lib/auth';
import {
  type IntelligenceCapabilities,
  type IntelligenceDashboard,
  fetchIntelligenceDashboard,
  fetchIntelligenceStatus,
} from '@/lib/intelligenceApi';

const DASHBOARDS = [
  { id: 'executive', label: 'Executive' },
  { id: 'operations', label: 'Operations' },
  { id: 'agent_performance', label: 'Agent performance' },
  { id: 'conversation', label: 'Conversations' },
  { id: 'payments', label: 'Payments' },
  { id: 'language', label: 'Language' },
] as const;

function formatValue(key: string, value: unknown): string {
  if (value == null) return '—';
  if (typeof value === 'number') {
    if (key.includes('rate') || key.includes('resolution') || key.includes('usage')) {
      return `${(value * 100).toFixed(1)}%`;
    }
    return value.toLocaleString();
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, number>)
      .slice(0, 6)
      .map(([key, count]) => `${key}: ${count}`)
      .join(' · ');
  }
  return String(value);
}

export default function IntelligencePage() {
  const auth = useAuth();
  const { orgContext } = useOrgConfig();
  const organizationId = orgContext?.organization_id ?? null;
  const [days, setDays] = useState(7);
  const [tab, setTab] = useState<(typeof DASHBOARDS)[number]['id']>('executive');
  const [caps, setCaps] = useState<IntelligenceCapabilities | null>(null);
  const [dashboard, setDashboard] = useState<IntelligenceDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!auth.isAuthenticated || !organizationId) return;
      setError(null);
      try {
        const status = await fetchIntelligenceStatus();
        setCaps(status);
        const data = await fetchIntelligenceDashboard(tab, organizationId, days);
        setDashboard(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load intelligence.');
        setDashboard(null);
      }
    };
    void load();
  }, [auth.isAuthenticated, organizationId, tab, days]);

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Business intelligence</h1>
          <p className="text-sm text-muted-foreground">
            Conversation outcomes, language mix, M-Pesa conversion, and generated insights.
            Phone numbers and payment amounts are hidden unless your role allows them.
          </p>
        </div>
        <Select value={String(days)} onValueChange={(value) => setDays(Number(value))}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Range" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {caps && !caps.payments ? (
        <p className="text-sm text-muted-foreground">
          KES totals are restricted for your role. Ask an owner or billing user for payment amounts.
        </p>
      ) : null}

      <Tabs value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
        <TabsList className="flex flex-wrap h-auto">
          {DASHBOARDS.map((item) => (
            <TabsTrigger key={item.id} value={item.id}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {DASHBOARDS.map((item) => (
          <TabsContent key={item.id} value={item.id} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {Object.entries(dashboard?.kpis || {}).map(([key, value]) => (
                <Card key={key}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium capitalize">
                      {key.replaceAll('_', ' ')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-xl font-semibold">{formatValue(key, value)}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Insights</CardTitle>
                <CardDescription>Generated from classified conversations, not call counts alone.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {(dashboard?.insights || []).map((insight) => (
                  <div key={insight.headline}>
                    <p className="font-medium">{insight.headline}</p>
                    {insight.detail ? (
                      <p className="text-sm text-muted-foreground">{insight.detail}</p>
                    ) : null}
                  </div>
                ))}
                {!dashboard?.insights?.length ? (
                  <p className="text-sm text-muted-foreground">No insights for this window yet.</p>
                ) : null}
              </CardContent>
            </Card>
            {item.id === 'conversation' && dashboard?.conversations?.length ? (
              <Card>
                <CardHeader>
                  <CardTitle>Classified conversations</CardTitle>
                  <CardDescription>
                    Labels only. Excerpts appear if your role includes conversation PII access.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {dashboard.conversations.slice(0, 20).map((row, index) => (
                    <div key={String(row.id ?? index)} className="text-sm border-b pb-2">
                      <span className="font-medium">{String(row.category)}</span>
                      {' · '}
                      {String(row.intent || '—')}
                      {' · '}
                      {String(row.sentiment || '—')}
                      {' · '}
                      {String(row.outcome || '—')}
                      {row.redacted_excerpt ? (
                        <p className="text-muted-foreground mt-1">{String(row.redacted_excerpt)}</p>
                      ) : null}
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}
          </TabsContent>
        ))}
      </Tabs>
      <Button variant="outline" asChild>
        <Link href="/analytics">Back to call analytics</Link>
      </Button>
    </div>
  );
}
