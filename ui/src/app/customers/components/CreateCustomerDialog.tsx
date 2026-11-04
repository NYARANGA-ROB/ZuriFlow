'use client';

import { Plus } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { createCustomer,type CreateCustomerInput } from '@/lib/crmApi';

const LOCALE_OPTIONS = ['mixed', 'en', 'sw'];

export function CreateCustomerDialog({
  onCreated,
  initialPhone,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: {
  onCreated: (customerId: number) => void;
  initialPhone?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledOnOpenChange ?? setInternalOpen;
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    phone_e164: '',
    full_name: '',
    email: '',
    preferred_locale: 'mixed',
    account_reference: '',
    outstanding_balance: '',
  });

  const reset = () => {
    setForm({
      phone_e164: initialPhone ?? '',
      full_name: '',
      email: '',
      preferred_locale: 'mixed',
      account_reference: '',
      outstanding_balance: '',
    });
    setError(null);
  };

  useEffect(() => {
    if (open && initialPhone) {
      setForm((f) => ({ ...f, phone_e164: initialPhone }));
    }
  }, [open, initialPhone]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: CreateCustomerInput = {
      phone_e164: form.phone_e164.trim(),
      full_name: form.full_name.trim(),
      preferred_locale: form.preferred_locale,
    };

    if (form.email.trim()) {
      payload.email = form.email.trim();
    }

    if (form.account_reference.trim() && form.outstanding_balance.trim()) {
      payload.debt_account = {
        account_reference: form.account_reference.trim(),
        outstanding_balance: Number(form.outstanding_balance),
        currency: 'KES',
      };
    }

    try {
      const profile = await createCustomer(payload);
      setOpen(false);
      reset();
      onCreated(profile.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create customer');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Add customer
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add customer</DialogTitle>
          <DialogDescription>
            Create a CRM profile for collections, timeline tracking, and campaigns.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="phone">Phone (E.164)</Label>
            <Input
              id="phone"
              required
              placeholder="+254712345678"
              value={form.phone_e164}
              onChange={(e) => setForm((f) => ({ ...f, phone_e164: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">Full name</Label>
            <Input
              id="name"
              required
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email (optional)</Label>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label>Preferred locale</Label>
            <Select
              value={form.preferred_locale}
              onValueChange={(value) => setForm((f) => ({ ...f, preferred_locale: value }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LOCALE_OPTIONS.map((locale) => (
                  <SelectItem key={locale} value={locale}>
                    {locale}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="rounded-lg border p-3 space-y-3">
            <p className="text-sm font-medium">Debt account (optional)</p>
            <div className="space-y-2">
              <Label htmlFor="account_ref">Account reference</Label>
              <Input
                id="account_ref"
                value={form.account_reference}
                onChange={(e) => setForm((f) => ({ ...f, account_reference: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="balance">Outstanding balance (KES)</Label>
              <Input
                id="balance"
                type="number"
                min="0"
                value={form.outstanding_balance}
                onChange={(e) => setForm((f) => ({ ...f, outstanding_balance: e.target.value }))}
              />
            </div>
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
