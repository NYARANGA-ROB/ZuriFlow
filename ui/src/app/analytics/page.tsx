'use client';

import { format } from 'date-fns';
import { Activity, BarChart3, Phone, TrendingUp, Users } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useOrgConfig } from '@/context/OrgConfigContext';
import { useAuth } from '@/lib/auth';
import {
  type AdminSummary,
  type AnalyticsDays,
  type VoiceDashboardSummary,
  fetchAdminSummary,
  fetchVoiceDashboard,
} from '@/lib/analyticsApi';

import { LiveCallsPanel } from './components/LiveCallsPanel';

function MetricCard({
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

export default function AnalyticsPage() {
  const auth = useAuth();
  const { orgContext } = useOrgConfig();
  const organizationId = orgContext?.organization_id ?? null;

  const [days, setDays] = useState<AnalyticsDays>(7);
  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [voiceSummary, setVoiceSummary] = useState<VoiceDashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!auth.isAuthenticated) return;

      setLoading(true);
      setError(null);

      try {
        const adminSummary = await fetchAdminSummary(days);
        setSummary(adminSummary);

        if (organizationId) {
          try {
            const voice = await fetchVoiceDashboard(organizationId, days);
            setVoiceSummary(voice);
          } catch {
            setVoiceSummary(null);
          }
        } else {
          setVoiceSummary(null);
        }
      } catch (err) {
        console.error(err);
        setError('Unable to load analytics. Confirm admin operations is enabled for your org.');
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [auth.isAuthenticated, days, organizationId]);

  const business = summary?.business_call_analytics;
  const workflows = summary?.workflow_performance?.workflows ?? [];
  const voiceMetrics = voiceSummary?.metrics ?? {};

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
          <p className="text-sm text-muted-foreground">
            Operations overview for voice workflows, payments, and live call activity.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={String(days)}
            onValueChange={(value) => setDays(Number(value) as AnalyticsDays)}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" asChild>
            <Link href="/intelligence">Business intelligence</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/reports">Legacy reports</Link>
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-28" />
          ))}
        </div>
      ) : null}

      {error ? (
        <Card>
          <CardContent className="py-8 text-sm text-muted-foreground">{error}</CardContent>
        </Card>
      ) : null}

      {!loading && summary ? (
        <>
          <LiveCallsPanel />

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <MetricCard
              title="Total Calls"
              value={(business?.total_calls ?? summary.tenant?.total_calls ?? 0).toLocaleString()}
              hint={`Window ending ${format(new Date(summary.to_ts * 1000), 'MMM d, yyyy')}`}
              icon={Phone}
            />
            <MetricCard
              title="Live Calls"
              value={(summary.live_calls?.active_count ?? 0).toLocaleString()}
              hint="Currently active sessions"
              icon={Activity}
            />
            <MetricCard
              title="Active Workflows"
              value={(summary.tenant?.active_workflows ?? 0).toLocaleString()}
              hint={`${summary.tenant?.member_count ?? 0} team members`}
              icon={Users}
            />
            <MetricCard
              title="Escalations"
              value={String((summary.escalations as { total?: number } | undefined)?.total ?? 0)}
              hint="Human handoffs in range"
              icon={TrendingUp}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Kenya conversational intelligence</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-between gap-4">
              <p className="text-sm text-muted-foreground">
                Language mix, Sheng usage, clarification, and escalation rates — with per-turn
                confidence, not a claim of perfect understanding.
              </p>
              <Button variant="outline" asChild>
                <Link href="/kenya-intelligence">Open dashboard</Link>
              </Button>
            </CardContent>
          </Card>

          {business?.kpis && Object.keys(business.kpis).length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Business KPIs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {Object.entries(business.kpis).map(([key, kpi]) => (
                    <div key={key} className="rounded-lg border p-4">
                      <div className="text-sm font-medium">{kpi.name || key}</div>
                      <div className="text-xl font-semibold mt-1">
                        {kpi.value ?? kpi.rate ?? kpi.count ?? '—'}
                      </div>
                      {kpi.rate != null ? (
                        <div className="text-xs text-muted-foreground">
                          Success rate {(kpi.rate * 100).toFixed(1)}%
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          {voiceSummary ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Voice Analytics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                  {Object.entries(voiceMetrics).slice(0, 8).map(([metric, value]) => (
                    <div key={metric} className="rounded-lg border p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">
                        {metric.replace(/_/g, ' ')}
                      </div>
                      <div className="text-lg font-semibold mt-1">
                        {typeof value === 'object' && value !== null && 'count' in value
                          ? String((value as { count?: number }).count ?? 0)
                          : String(value ?? '—')}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Workflow Performance</CardTitle>
            </CardHeader>
            <CardContent>
              {workflows.length === 0 ? (
                <p className="text-sm text-muted-foreground">No workflow activity in this range.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="py-2 pr-4">Workflow</th>
                        <th className="py-2 pr-4">Runs</th>
                        <th className="py-2 pr-4">Completed</th>
                        <th className="py-2">Avg duration (s)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {workflows.map((row) => (
                        <tr key={row.workflow_id} className="border-b last:border-0">
                          <td className="py-2 pr-4 font-medium">
                            {row.workflow_name || `Workflow ${row.workflow_id}`}
                          </td>
                          <td className="py-2 pr-4">{row.run_count ?? 0}</td>
                          <td className="py-2 pr-4">{row.completed_count ?? 0}</td>
                          <td className="py-2">
                            {row.avg_duration_s != null ? row.avg_duration_s.toFixed(1) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
