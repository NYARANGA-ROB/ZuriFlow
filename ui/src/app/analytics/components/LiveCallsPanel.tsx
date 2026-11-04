'use client';

import { Loader2, Radio } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { client } from '@/client/client.gen';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/lib/auth';
import { buildLiveDashboardWsUrl } from '@/lib/liveDashboardWs';

interface LivePayload {
  type: string;
  timestamp: number;
  payload?: {
    live_calls?: {
      active_count?: number;
      calls?: Array<Record<string, unknown>>;
    };
    tenant?: {
      total_calls?: number;
    };
  };
}

function buildWsUrl(token: string): string {
  const baseUrl = client.getConfig().baseUrl || window.location.origin;
  return buildLiveDashboardWsUrl(baseUrl, token);
}

export function LiveCallsPanel() {
  const { getAccessToken, isAuthenticated } = useAuth();
  const [connected, setConnected] = useState(false);
  const [snapshot, setSnapshot] = useState<LivePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    const connect = async () => {
      if (!isAuthenticated) return;

      try {
        const token = await getAccessToken();
        const ws = new WebSocket(buildWsUrl(token));
        wsRef.current = ws;

        ws.onopen = () => {
          if (!cancelled) {
            setConnected(true);
            setError(null);
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as LivePayload;
            if (!cancelled) setSnapshot(data);
          } catch {
            // ignore malformed frames
          }
        };

        ws.onerror = () => {
          if (!cancelled) setError('Live dashboard connection failed');
        };

        ws.onclose = () => {
          if (!cancelled) setConnected(false);
        };
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unable to connect live feed');
        }
      }
    };

    void connect();

    return () => {
      cancelled = true;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [getAccessToken, isAuthenticated]);

  const liveCalls = snapshot?.payload?.live_calls;
  const calls = liveCalls?.calls ?? [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base flex items-center gap-2">
          <Radio className="h-4 w-4" />
          Live operations
        </CardTitle>
        <Badge variant={connected ? 'default' : 'secondary'}>
          {connected ? 'Connected' : 'Disconnected'}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {!snapshot ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Waiting for live snapshot...
          </div>
        ) : (
          <>
            <div className="text-sm text-muted-foreground">
              {liveCalls?.active_count ?? 0} active call
              {(liveCalls?.active_count ?? 0) === 1 ? '' : 's'}
            </div>
            {calls.length === 0 ? (
              <p className="text-sm text-muted-foreground">No active calls right now.</p>
            ) : (
              <div className="space-y-2">
                {calls.slice(0, 8).map((call, index) => (
                  <div key={index} className="rounded-md border px-3 py-2 text-sm">
                    <div className="font-medium">
                      Run {String(call.workflow_run_id ?? call.run_id ?? '—')}
                    </div>
                    <div className="text-muted-foreground">
                      {String(call.workflow_name ?? call.status ?? 'in progress')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
