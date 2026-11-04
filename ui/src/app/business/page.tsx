'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useAuth } from '@/lib/auth';
import { fetchBusinessHealth, importWebsite, sendInterview } from '@/lib/businessTwinApi';

export default function BusinessInformationPage() {
  const { isAuthenticated, redirectToLogin, loading } = useAuth();
  const [health, setHealth] = useState<Awaited<ReturnType<typeof fetchBusinessHealth>> | null>(null);
  const [url, setUrl] = useState('');
  const [talk, setTalk] = useState('');
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    setHealth(await fetchBusinessHealth());
  }, []);

  useEffect(() => {
    if (!loading && !isAuthenticated) redirectToLogin();
  }, [isAuthenticated, loading, redirectToLogin]);

  useEffect(() => {
    if (isAuthenticated) load().catch(() => setStatus('Could not load business information.'));
  }, [isAuthenticated, load]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-bold">Business Information</h1>
        <p className="text-muted-foreground">
          Tell ZuriFlow about your business once. We keep your agent updated from your website,
          documents, and connected systems — with your approval for important changes.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Business health</CardTitle>
          <CardDescription>
            Overall freshness {health ? `${health.overall_freshness}%` : '—'}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {health &&
            Object.entries(health.sections).map(([key, section]) => (
              <div key={key} className="rounded-md border p-3 text-sm">
                <div className="font-medium">{section.label}</div>
                <div className="text-muted-foreground">{section.state}</div>
              </div>
            ))}
        </CardContent>
      </Card>
      <div className="flex gap-3">
        <Button asChild>
          <Link href="/business/changes">Latest Changes</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/setup">Business setup</Link>
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Import from website</CardTitle>
          <CardDescription>We only read public pages. You approve what the agent can say.</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://yourbusiness.co.ke" />
          <Button
            onClick={async () => {
              try {
                await importWebsite(url);
                setStatus('Website imported. Review findings in Latest Changes.');
                await load();
              } catch (err) {
                setStatus(err instanceof Error ? err.message : 'Import failed');
              }
            }}
          >
            Import
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Tell ZuriFlow about your business</CardTitle>
          <CardDescription>Talk or type. Nothing is published until you confirm it.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Textarea
            value={talk}
            onChange={(e) => setTalk(e.target.value)}
            placeholder="We are a clinic in Kisumu. Open 8am to 5pm. We accept M-Pesa..."
          />
          <Button
            onClick={async () => {
              try {
                await sendInterview(talk);
                setStatus('Extracted for review. Confirm in Latest Changes before customers hear it.');
              } catch (err) {
                setStatus(err instanceof Error ? err.message : 'Could not extract');
              }
            }}
          >
            Extract for review
          </Button>
        </CardContent>
      </Card>
      {status && <p className="text-sm text-muted-foreground">{status}</p>}
      {health?.alerts?.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Needs attention</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {health.alerts.map((alert) => (
              <div key={alert.id} className="text-sm">
                <div className="font-medium">{alert.title}</div>
                <div className="text-muted-foreground">{alert.body}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
