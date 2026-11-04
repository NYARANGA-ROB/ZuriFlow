'use client';

import { GripVertical, Loader2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { APP_NAME } from "@/constants/branding";

import { client } from '@/client/client.gen';
import type { TelephonyConfigurationListItem } from '@/client/types.gen';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { detailFromError } from '@/lib/apiError';
import { useAuth } from '@/lib/auth';

interface FailoverConfiguration {
  enabled: boolean;
  configuration_ids: number[];
}

interface FailoverConfigurationCardProps {
  configurations: TelephonyConfigurationListItem[];
}

export function FailoverConfigurationCard({
  configurations,
}: FailoverConfigurationCardProps) {
  const { getAccessToken } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = await getAccessToken();
      const response = await client.get({
        url: '/api/v1/organizations/telephony-failover',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.error) throw new Error(detailFromError(response.error));
      const data = response.data as FailoverConfiguration;
      setEnabled(Boolean(data.enabled));
      setSelectedIds(data.configuration_ids ?? []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load failover settings');
    } finally {
      setLoading(false);
    }
  }, [getAccessToken]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleConfig = (configId: number) => {
    setSelectedIds((current) =>
      current.includes(configId)
        ? current.filter((id) => id !== configId)
        : [...current, configId],
    );
  };

  const moveConfig = (index: number, direction: -1 | 1) => {
    setSelectedIds((current) => {
      const next = [...current];
      const target = index + direction;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      const token = await getAccessToken();
      const response = await client.put({
        url: '/api/v1/organizations/telephony-failover',
        headers: { Authorization: `Bearer ${token}` },
        body: {
          enabled,
          configuration_ids: selectedIds,
        },
      });
      if (response.error) throw new Error(detailFromError(response.error));
      toast.success('Failover configuration saved');
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save failover settings');
    } finally {
      setSaving(false);
    }
  };

  const configById = new Map(configurations.map((item) => [item.id, item]));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Carrier failover</CardTitle>
        <CardDescription>
          When outbound dialing fails on one provider, {APP_NAME} tries the next configuration in
          order. The campaign or test call primary config is always attempted first.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="font-medium">Enable failover</div>
            <p className="text-sm text-muted-foreground">
              Retry outbound calls on alternate telephony configurations.
            </p>
          </div>
          <Switch checked={enabled} onCheckedChange={setEnabled} disabled={loading} />
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading failover chain...
          </div>
        ) : (
          <div className="space-y-2">
            {selectedIds.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Select configurations below to build the failover chain.
              </p>
            ) : (
              selectedIds.map((configId, index) => {
                const config = configById.get(configId);
                return (
                  <div
                    key={configId}
                    className="flex items-center gap-2 rounded-md border px-3 py-2"
                  >
                    <GripVertical className="h-4 w-4 text-muted-foreground" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">
                        {config?.name ?? `Configuration ${configId}`}
                      </div>
                      {config ? (
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="secondary">{config.provider}</Badge>
                          <span className="text-xs text-muted-foreground">Priority {index + 1}</span>
                        </div>
                      ) : null}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => moveConfig(index, -1)}
                      disabled={index === 0}
                    >
                      Up
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => moveConfig(index, 1)}
                      disabled={index === selectedIds.length - 1}
                    >
                      Down
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleConfig(configId)}
                    >
                      Remove
                    </Button>
                  </div>
                );
              })
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {configurations
            .filter((config) => !selectedIds.includes(config.id))
            .map((config) => (
              <Button
                key={config.id}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => toggleConfig(config.id)}
              >
                Add {config.name}
              </Button>
            ))}
        </div>

        <Button onClick={save} disabled={saving || loading}>
          {saving ? 'Saving...' : 'Save failover chain'}
        </Button>
      </CardContent>
    </Card>
  );
}
