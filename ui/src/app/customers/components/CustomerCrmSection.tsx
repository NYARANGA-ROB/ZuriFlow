'use client';

import { format, parseISO } from 'date-fns';
import { Plus } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  type AuditLogEntry,
  type CustomerProfile,
  listAuditLogs,
  recordCall,
  recordEscalation,
  recordPayment,
  upsertDebtAccount,
} from '@/lib/crmApi';

function formatCurrency(amount: number, currency = 'KES') {
  return new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatTs(value: string | null) {
  if (!value) return '—';
  try {
    return format(parseISO(value), 'MMM d, yyyy · h:mm a');
  } catch {
    return value;
  }
}

export function CustomerCrmSection({
  profile,
  onRefresh,
}: {
  profile: CustomerProfile;
  onRefresh: () => void;
}) {
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(true);

  const loadAudit = useCallback(async () => {
    setLoadingAudit(true);
    try {
      const rows = await listAuditLogs({ customerId: profile.id, limit: 50 });
      setAuditLogs(rows);
    } catch {
      setAuditLogs([]);
    } finally {
      setLoadingAudit(false);
    }
  }, [profile.id]);

  useEffect(() => {
    void loadAudit();
  }, [loadAudit]);

  const refreshAll = () => {
    onRefresh();
    void loadAudit();
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Debt accounts</CardTitle>
            <DebtAccountDialog customerId={profile.id} onSaved={refreshAll} />
          </CardHeader>
          <CardContent>
            {profile.debt_accounts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No debt accounts.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {profile.debt_accounts.map((account, index) => (
                  <li key={String(account.id ?? index)} className="rounded-lg border p-3">
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">{String(account.account_reference ?? 'Account')}</span>
                      <Badge variant="outline">{String(account.status ?? 'active')}</Badge>
                    </div>
                    <p className="mt-1 text-muted-foreground">
                      {typeof account.outstanding_balance === 'number'
                        ? formatCurrency(
                            account.outstanding_balance,
                            String(account.currency ?? 'KES'),
                          )
                        : '—'}
                      {typeof account.days_past_due === 'number'
                        ? ` · ${account.days_past_due} days past due`
                        : ''}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Payments</CardTitle>
            <RecordPaymentDialog customerId={profile.id} onSaved={refreshAll} />
          </CardHeader>
          <CardContent>
            {profile.payment_history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No payments recorded.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {profile.payment_history.slice(0, 8).map((payment, index) => (
                  <li key={String(payment.id ?? index)} className="flex justify-between gap-2">
                    <span>{String(payment.status ?? 'payment')}</span>
                    <span className="text-muted-foreground">
                      {typeof payment.amount === 'number'
                        ? formatCurrency(payment.amount, String(payment.currency ?? 'KES'))
                        : '—'}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Calls</CardTitle>
            <RecordCallDialog profile={profile} onSaved={refreshAll} />
          </CardHeader>
          <CardContent>
            {profile.call_history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No calls recorded.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {profile.call_history.slice(0, 8).map((call, index) => (
                  <li key={String(call.id ?? index)}>
                    <span className="font-medium">
                      {String(call.disposition ?? call.call_type ?? 'Call')}
                    </span>
                    {call.summary ? (
                      <p className="text-muted-foreground">{String(call.summary)}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Escalations</CardTitle>
            <RecordEscalationDialog customerId={profile.id} onSaved={refreshAll} />
          </CardHeader>
          <CardContent>
            {profile.escalation_history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No escalations recorded.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {profile.escalation_history.slice(0, 8).map((item, index) => (
                  <li key={String(item.id ?? index)} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(item.reason ?? 'Escalation')}</span>
                      <Badge variant="outline">{String(item.risk_level ?? 'medium')}</Badge>
                    </div>
                    {item.queue_name ? (
                      <p className="mt-1 text-muted-foreground">Queue: {String(item.queue_name)}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Audit log</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingAudit ? (
            <p className="text-sm text-muted-foreground">Loading audit log…</p>
          ) : auditLogs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No audit entries for this customer.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {auditLogs.map((entry) => (
                <li key={entry.id} className="flex flex-wrap items-center justify-between gap-2 border-b pb-2 last:border-0">
                  <span>
                    <span className="font-medium">{entry.action}</span>
                    <span className="text-muted-foreground"> · {entry.resource_type}</span>
                  </span>
                  <span className="text-xs text-muted-foreground">{formatTs(entry.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DebtAccountDialog({
  customerId,
  onSaved,
}: {
  customerId: number;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    account_reference: '',
    outstanding_balance: '',
    days_past_due: '0',
  });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await upsertDebtAccount(customerId, {
        account_reference: form.account_reference.trim(),
        outstanding_balance: Number(form.outstanding_balance),
        days_past_due: Number(form.days_past_due) || 0,
      });
      setOpen(false);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus className="mr-1 h-4 w-4" />
          Add / update
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Debt account</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-2">
            <Label>Account reference</Label>
            <Input
              required
              value={form.account_reference}
              onChange={(e) => setForm((f) => ({ ...f, account_reference: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label>Outstanding balance (KES)</Label>
            <Input
              required
              type="number"
              min="0"
              value={form.outstanding_balance}
              onChange={(e) => setForm((f) => ({ ...f, outstanding_balance: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label>Days past due</Label>
            <Input
              type="number"
              min="0"
              value={form.days_past_due}
              onChange={(e) => setForm((f) => ({ ...f, days_past_due: e.target.value }))}
            />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RecordPaymentDialog({
  customerId,
  onSaved,
}: {
  customerId: number;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [amount, setAmount] = useState('');
  const [receipt, setReceipt] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await recordPayment(customerId, {
        amount: Number(amount),
        receipt_reference: receipt.trim() || null,
      });
      setOpen(false);
      onSaved();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus className="mr-1 h-4 w-4" />
          Record
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Record payment</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-2">
            <Label>Amount (KES)</Label>
            <Input required type="number" min="0" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Receipt reference</Label>
            <Input value={receipt} onChange={(e) => setReceipt(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={submitting}>Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RecordCallDialog({
  profile,
  onSaved,
}: {
  profile: CustomerProfile;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [disposition, setDisposition] = useState('');
  const [summary, setSummary] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await recordCall(profile.id, {
        phone_e164: profile.phone_e164,
        disposition: disposition.trim() || null,
        summary: summary.trim() || null,
      });
      setOpen(false);
      onSaved();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus className="mr-1 h-4 w-4" />
          Record
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Record call</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-2">
            <Label>Disposition</Label>
            <Input value={disposition} onChange={(e) => setDisposition(e.target.value)} placeholder="answered, no_answer…" />
          </div>
          <div className="space-y-2">
            <Label>Summary</Label>
            <Textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={3} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={submitting}>Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RecordEscalationDialog({
  customerId,
  onSaved,
}: {
  customerId: number;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reason, setReason] = useState('');
  const [queue, setQueue] = useState('human');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await recordEscalation(customerId, {
        reason: reason.trim(),
        queue_name: queue.trim() || null,
      });
      setOpen(false);
      onSaved();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus className="mr-1 h-4 w-4" />
          Record
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Record escalation</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-2">
            <Label>Reason</Label>
            <Textarea required value={reason} onChange={(e) => setReason(e.target.value)} rows={3} />
          </div>
          <div className="space-y-2">
            <Label>Queue</Label>
            <Input value={queue} onChange={(e) => setQueue(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={submitting}>Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
