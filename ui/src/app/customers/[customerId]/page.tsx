'use client';

import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { CustomerCrmSection } from '@/app/customers/components/CustomerCrmSection';
import { CustomerTimelinePanel } from '@/app/customers/components/CustomerTimeline';
import { EditCustomerDialog } from '@/app/customers/components/EditCustomerDialog';
import { JourneyStateBadge } from '@/app/customers/components/JourneyStateBadge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/lib/auth';
import {
  type CustomerProfile,
  fetchCrmStatus,
  getCustomerProfile,
} from '@/lib/crmApi';
import {
  type CustomerTimeline,
  fetchCustomerTimeline,
  fetchTimelineStatus,
  type TimelineDays,
} from '@/lib/customerTimelineApi';

function formatCurrency(amount: number, currency = 'KES') {
  return new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function CustomerDetailPage() {
  const auth = useAuth();
  const params = useParams();
  const customerId = Number(params.customerId);

  const [crmEnabled, setCrmEnabled] = useState<boolean | null>(null);
  const [timelineEnabled, setTimelineEnabled] = useState<boolean | null>(null);
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [timeline, setTimeline] = useState<CustomerTimeline | null>(null);
  const [days, setDays] = useState<TimelineDays>(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(customerId)) {
      setError('Invalid customer id');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [crmStatus, timelineStatus] = await Promise.all([
        fetchCrmStatus(),
        fetchTimelineStatus(),
      ]);
      setCrmEnabled(crmStatus.enabled);
      setTimelineEnabled(timelineStatus.enabled);

      if (!crmStatus.enabled) {
        setLoading(false);
        return;
      }

      const customerProfile = await getCustomerProfile(customerId);
      setProfile(customerProfile);

      if (timelineStatus.enabled) {
        const customerTimeline = await fetchCustomerTimeline(customerId, days);
        setTimeline(customerTimeline);
      } else {
        setTimeline(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load customer');
      setProfile(null);
      setTimeline(null);
    } finally {
      setLoading(false);
    }
  }, [customerId, days]);

  useEffect(() => {
    if (!auth.isAuthenticated) return;
    void load();
  }, [auth.isAuthenticated, load]);

  if (!auth.isAuthenticated) {
    return null;
  }

  if (crmEnabled === false) {
    return (
      <div className="container max-w-4xl py-8">
        <Card>
          <CardHeader>
            <CardTitle>Customer profile</CardTitle>
            <CardDescription>CRM is disabled on this deployment.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const journeyState = timeline?.journey_state ?? 'unknown';

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/customers">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="min-w-0 flex-1">
          {loading ? (
            <Skeleton className="h-8 w-48" />
          ) : profile ? (
            <>
              <h1 className="truncate text-2xl font-semibold tracking-tight">{profile.full_name}</h1>
              <p className="text-sm text-muted-foreground">{profile.phone_e164}</p>
            </>
          ) : (
            <h1 className="text-2xl font-semibold tracking-tight">Customer</h1>
          )}
        </div>
        {!loading && timelineEnabled ? (
          <JourneyStateBadge state={journeyState} />
        ) : null}
        {!loading && profile ? (
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href={`/customers/lookup?phone=${encodeURIComponent(profile.phone_e164)}`}>
                Timeline lookup
              </Link>
            </Button>
            <EditCustomerDialog
              profile={profile}
              onUpdated={(updated) => {
                setProfile(updated);
                void load();
              }}
            />
          </div>
        ) : null}
      </div>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-3">
          <Skeleton className="h-28 md:col-span-1" />
          <Skeleton className="h-28 md:col-span-2" />
          <Skeleton className="h-64 md:col-span-3" />
        </div>
      ) : profile ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Outstanding balance</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  {formatCurrency(profile.total_outstanding)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {profile.debt_accounts.length} debt account
                  {profile.debt_accounts.length === 1 ? '' : 's'}
                </p>
              </CardContent>
            </Card>

            <Card className="md:col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Profile</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <span className="text-muted-foreground">Email</span>
                  <p>{profile.email ?? '—'}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Locale</span>
                  <p>{profile.preferred_locale}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Status</span>
                  <p>
                    <Badge variant={profile.is_active ? 'default' : 'secondary'}>
                      {profile.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">External CRM ID</span>
                  <p>{profile.external_crm_id ?? '—'}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {timelineEnabled ? (
            <Tabs defaultValue="timeline" className="space-y-4">
              <TabsList>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
                <TabsTrigger value="crm">CRM activity</TabsTrigger>
              </TabsList>

              <TabsContent value="timeline" className="space-y-4">
                <div className="flex items-center justify-between gap-4">
                  <p className="text-sm text-muted-foreground">
                    Cross-channel activity from voice, WhatsApp, email, M-Pesa, and campaigns.
                  </p>
                  <Select
                    value={String(days)}
                    onValueChange={(value) => setDays(Number(value) as TimelineDays)}
                  >
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

                {timeline ? (
                  <CustomerTimelinePanel
                    entries={timeline.entries}
                    channelsActive={timeline.channels_active}
                  />
                ) : null}
              </TabsContent>

              <TabsContent value="crm">
                <CustomerCrmSection profile={profile} onRefresh={() => void load()} />
              </TabsContent>
            </Tabs>
          ) : (
            <CustomerCrmSection profile={profile} onRefresh={() => void load()} />
          )}

          {timelineEnabled === false ? (
            <Card>
              <CardContent className="pt-6 text-sm text-muted-foreground">
                Customer timeline is disabled. Enable <code>CUSTOMER_TIMELINE_ENABLED</code> to see
                omnichannel activity here.
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
