'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useAuth } from '@/lib/auth';
import {
  checkComplianceText,
  type ComplianceCheckResult,
  type DebtSessionDetail,
  fetchDebtCollectionStatus,
  getComplianceAudit,
  getDebtSession,
} from '@/lib/debtCollectionApi';

export default function DebtCollectionPage() {
  const auth = useAuth();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [templateId, setTemplateId] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [session, setSession] = useState<DebtSessionDetail | null>(null);
  const [auditCount, setAuditCount] = useState<number | null>(null);
  const [complianceText, setComplianceText] = useState('');
  const [complianceResult, setComplianceResult] = useState<ComplianceCheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!auth.isAuthenticated) return;
    void (async () => {
      setLoading(true);
      const status = await fetchDebtCollectionStatus();
      setEnabled(status.enabled);
      setTemplateId(status.template_id);
      setLoading(false);
    })();
  }, [auth.isAuthenticated]);

  const lookupSession = useCallback(async () => {
    const id = sessionId.trim();
    if (!id) return;
    setError(null);
    try {
      const [detail, audit] = await Promise.all([
        getDebtSession(id),
        getComplianceAudit(id).catch(() => null),
      ]);
      setSession(detail);
      setAuditCount(audit?.violation_count ?? null);
    } catch (err) {
      setSession(null);
      setAuditCount(null);
      setError(err instanceof Error ? err.message : 'Session not found');
    }
  }, [sessionId]);

  const runComplianceCheck = async () => {
    if (!complianceText.trim()) return;
    setChecking(true);
    setError(null);
    try {
      const result = await checkComplianceText(complianceText.trim(), 'agent');
      setComplianceResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Compliance check failed');
    } finally {
      setChecking(false);
    }
  };

  if (!auth.isAuthenticated) return null;

  if (enabled === false) {
    return (
      <div className="container max-w-5xl py-8">
        <Card>
          <CardHeader>
            <CardTitle>Debt collection</CardTitle>
            <CardDescription>
              Disabled. Set <code>DEBT_COLLECTION_ENABLED=true</code> on the API.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Debt collection</h1>
        <p className="text-sm text-muted-foreground">
          Session monitoring and compliance guardrails for collections workflows.
        </p>
      </div>

      {loading ? (
        <Skeleton className="h-24 w-full" />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Workflow status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Badge>Enabled</Badge>
            {templateId ? <Badge variant="outline">Template: {templateId}</Badge> : null}
          </CardContent>
        </Card>
      )}

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Session lookup</CardTitle>
            <CardDescription>Inspect an active or completed debt collection session.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input
                placeholder="Session ID"
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
              />
              <Button onClick={() => void lookupSession()}>Lookup</Button>
            </div>
            {session ? (
              <div className="space-y-2 rounded-lg border p-3 text-sm">
                <p>
                  <span className="font-medium">Outcome:</span>{' '}
                  <Badge variant="outline">{session.negotiation_outcome}</Badge>
                </p>
                <p>
                  <span className="font-medium">Escalation risk:</span>{' '}
                  <Badge variant="outline">{session.escalation_risk}</Badge>
                </p>
                <p>
                  Rounds: {session.negotiation_rounds} · Refusals: {session.refusal_count}
                </p>
                {auditCount != null ? (
                  <p className="text-muted-foreground">Compliance violations: {auditCount}</p>
                ) : null}
                {session.account ? (
                  <p>
                    Balance: {String(session.account.outstanding_balance)}{' '}
                    {String(session.account.currency ?? 'KES')}
                  </p>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Compliance checker</CardTitle>
            <CardDescription>Validate agent script text before it goes live.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label>Agent utterance</Label>
              <Textarea
                rows={5}
                value={complianceText}
                onChange={(e) => setComplianceText(e.target.value)}
                placeholder="Paste proposed collections script…"
              />
            </div>
            <Button onClick={() => void runComplianceCheck()} disabled={checking}>
              {checking ? 'Checking…' : 'Check compliance'}
            </Button>
            {complianceResult ? (
              <div className="rounded-lg border p-3 text-sm">
                <Badge variant={complianceResult.allowed ? 'default' : 'destructive'}>
                  {complianceResult.allowed ? 'Allowed' : 'Blocked'}
                </Badge>
                {complianceResult.violations.length > 0 ? (
                  <ul className="mt-2 list-disc pl-5 text-muted-foreground">
                    {complianceResult.violations.map((v) => (
                      <li key={v}>{v}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
