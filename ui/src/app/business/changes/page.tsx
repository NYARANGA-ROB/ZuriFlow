'use client';

import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/lib/auth';
import { decideChange, fetchBusinessChanges } from '@/lib/businessTwinApi';

export default function BusinessChangesPage() {
  const { isAuthenticated, redirectToLogin, loading } = useAuth();
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchBusinessChanges>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setData(await fetchBusinessChanges());
  }, []);

  useEffect(() => {
    if (!loading && !isAuthenticated) redirectToLogin();
  }, [isAuthenticated, loading, redirectToLogin]);

  useEffect(() => {
    if (isAuthenticated) load().catch(() => setError('Could not load changes.'));
  }, [isAuthenticated, load]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-bold">Latest Changes</h1>
        <p className="text-muted-foreground">
          Information that needs review, conflicts between sources, and failed updates.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {data?.conflicts.map((conflict) => (
        <Card key={`c-${conflict.id}`}>
          <CardHeader>
            <CardTitle>Business information conflict detected</CardTitle>
            <CardDescription>{conflict.field}</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {conflict.source_a}: {conflict.value_a} versus {conflict.source_b}: {conflict.value_b}
          </CardContent>
        </Card>
      ))}
      {data?.changes.map((change) => (
        <Card key={change.id}>
          <CardHeader>
            <CardTitle>{change.field}</CardTitle>
            <CardDescription>
              Source {change.source} · Confidence {Math.round(change.confidence * 100)}% · Risk{' '}
              {change.risk.toUpperCase()}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>Old: {change.old_value || '—'}</div>
            <div>New: {change.new_value || '—'}</div>
            <div className="flex gap-2">
              <Button
                onClick={async () => {
                  await decideChange(change.id, 'approved');
                  await load();
                }}
              >
                Approve
              </Button>
              <Button
                variant="outline"
                onClick={async () => {
                  await decideChange(change.id, 'rejected');
                  await load();
                }}
              >
                Reject
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
      {data && data.changes.length === 0 && data.conflicts.length === 0 && (
        <p className="text-sm text-muted-foreground">No pending changes.</p>
      )}
      {data?.failed_syncs.map((run) => (
        <p key={run.id} className="text-sm text-muted-foreground">
          Update failed: {run.error || run.status}
        </p>
      ))}
    </div>
  );
}
