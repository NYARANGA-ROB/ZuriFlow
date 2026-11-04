'use client';

import { ArrowLeft, Phone, Search } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { CustomerTimelinePanel } from '@/app/customers/components/CustomerTimeline';
import { JourneyStateBadge } from '@/app/customers/components/JourneyStateBadge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/lib/auth';
import { getCustomerByPhone } from '@/lib/crmApi';
import {
  type CustomerTimeline,
  fetchPhoneTimeline,
  fetchTimelineStatus,
  type TimelineDays,
} from '@/lib/customerTimelineApi';

export default function CustomerLookupPage() {
  const auth = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialPhone = searchParams.get('phone') ?? '';

  const [phone, setPhone] = useState(initialPhone);
  const [timelineEnabled, setTimelineEnabled] = useState<boolean | null>(null);
  const [timeline, setTimeline] = useState<CustomerTimeline | null>(null);
  const [crmCustomerId, setCrmCustomerId] = useState<number | null>(null);
  const [days, setDays] = useState<TimelineDays>(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prevDays = useRef(days);

  const lookup = useCallback(async (phoneValue: string, windowDays: TimelineDays) => {
    const normalized = phoneValue.trim();
    if (!normalized) {
      setError('Enter a phone number');
      return;
    }

    setLoading(true);
    setError(null);
    setTimeline(null);
    setCrmCustomerId(null);

    try {
      const status = await fetchTimelineStatus();
      setTimelineEnabled(status.enabled);
      if (!status.enabled) {
        return;
      }

      const [phoneTimeline, crmProfile] = await Promise.all([
        fetchPhoneTimeline(normalized, windowDays),
        getCustomerByPhone(normalized).catch(() => null),
      ]);

      setTimeline(phoneTimeline);
      setCrmCustomerId(crmProfile?.id ?? phoneTimeline.customer_id ?? null);

      const params = new URLSearchParams({ phone: normalized });
      router.replace(`/customers/lookup?${params.toString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lookup failed');
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!auth.isAuthenticated) return;

    void (async () => {
      const status = await fetchTimelineStatus();
      setTimelineEnabled(status.enabled);
      if (status.enabled && initialPhone.trim()) {
        await lookup(initialPhone, days);
      }
    })();
    // Initial load only — days changes handled separately.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isAuthenticated]);

  useEffect(() => {
    if (prevDays.current === days || !phone.trim() || !timeline) {
      prevDays.current = days;
      return;
    }
    prevDays.current = days;
    void lookup(phone.trim(), days);
  }, [days, lookup, phone, timeline]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void lookup(phone, days);
  };

  if (!auth.isAuthenticated) {
    return null;
  }

  if (timelineEnabled === false) {
    return (
      <div className="container max-w-4xl py-8">
        <Card>
          <CardHeader>
            <CardTitle>Phone lookup</CardTitle>
            <CardDescription>
              Customer timeline is disabled. Enable <code>CUSTOMER_TIMELINE_ENABLED</code> to use
              phone lookup.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/customers">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight">Phone lookup</h1>
          <p className="text-sm text-muted-foreground">
            View omnichannel activity by phone — even before a CRM profile exists.
          </p>
        </div>
        <Phone className="hidden h-8 w-8 text-muted-foreground sm:block" />
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+254712345678"
            className="pl-9"
          />
        </div>
        <Select
          value={String(days)}
          onValueChange={(value) => setDays(Number(value) as TimelineDays)}
        >
          <SelectTrigger className="w-full sm:w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
          </SelectContent>
        </Select>
        <Button type="submit" disabled={loading}>
          {loading ? 'Looking up…' : 'Lookup'}
        </Button>
      </form>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <Skeleton className="h-64 w-full" />
      ) : timeline ? (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <p className="text-lg font-medium">
                {timeline.full_name ?? 'Unknown customer'}
              </p>
              <p className="text-sm text-muted-foreground">{timeline.phone_e164}</p>
            </div>
            <JourneyStateBadge state={timeline.journey_state} />
            {crmCustomerId ? (
              <Button variant="secondary" size="sm" asChild>
                <Link href={`/customers/${crmCustomerId}`}>Open CRM profile</Link>
              </Button>
            ) : (
              <Button variant="outline" size="sm" asChild>
                <Link href={`/customers?phone=${encodeURIComponent(timeline.phone_e164)}`}>
                  Create CRM profile
                </Link>
              </Button>
            )}
          </div>

          <CustomerTimelinePanel
            entries={timeline.entries}
            channelsActive={timeline.channels_active}
          />
        </>
      ) : null}
    </div>
  );
}
