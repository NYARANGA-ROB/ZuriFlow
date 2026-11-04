'use client';

import { useCallback, useEffect, useState } from 'react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/lib/auth';
import { fetchAuditLogs, type AuditItem } from '@/lib/controlPlaneApi';

export default function AuditLogsPage() {
  const { isAuthenticated, redirectToLogin, loading } = useAuth();
  const [items, setItems] = useState<AuditItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await fetchAuditLogs();
    setItems(data.items);
  }, []);

  useEffect(() => {
    if (!loading && !isAuthenticated) redirectToLogin();
  }, [isAuthenticated, loading, redirectToLogin]);

  useEffect(() => {
    if (isAuthenticated) {
      load().catch(() => setError('Could not load audit logs.'));
    }
  }, [isAuthenticated, load]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 py-10 px-4">
      <div>
        <h1 className="text-2xl font-bold">Organization audit log</h1>
        <p className="text-muted-foreground">
          Workflow changes, payment settings, invitations, integrations, publishes, and API
          credentials.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Recent actions</CardTitle>
          <CardDescription>Newest first, scoped to this organization.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">No administrative actions recorded yet.</p>
          ) : (
            items.map((item) => (
              <div key={item.id} className="border rounded p-3">
                <p className="font-medium">{item.action.replaceAll('_', ' ')}</p>
                <p className="text-sm text-muted-foreground">{item.summary}</p>
                <p className="text-xs text-muted-foreground">
                  {item.resource_type}
                  {item.resource_id ? ` #${item.resource_id}` : ''} · {item.created_at}
                </p>
              </div>
            ))
          )}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
