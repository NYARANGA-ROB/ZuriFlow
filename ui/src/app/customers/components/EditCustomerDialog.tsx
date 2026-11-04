'use client';

import { Pencil } from 'lucide-react';
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
import { Switch } from '@/components/ui/switch';
import { type CustomerProfile, updateCustomer } from '@/lib/crmApi';

const LOCALE_OPTIONS = ['mixed', 'en', 'sw'];

export function EditCustomerDialog({
  profile,
  onUpdated,
}: {
  profile: CustomerProfile;
  onUpdated: (profile: CustomerProfile) => void;
}) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    phone_e164: profile.phone_e164,
    full_name: profile.full_name,
    email: profile.email ?? '',
    preferred_locale: profile.preferred_locale,
    external_crm_id: profile.external_crm_id ?? '',
    is_active: profile.is_active,
  });

  useEffect(() => {
    if (open) {
      setForm({
        phone_e164: profile.phone_e164,
        full_name: profile.full_name,
        email: profile.email ?? '',
        preferred_locale: profile.preferred_locale,
        external_crm_id: profile.external_crm_id ?? '',
        is_active: profile.is_active,
      });
      setError(null);
    }
  }, [open, profile]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const updated = await updateCustomer(profile.id, {
        phone_e164: form.phone_e164.trim(),
        full_name: form.full_name.trim(),
        email: form.email.trim() || null,
        preferred_locale: form.preferred_locale,
        external_crm_id: form.external_crm_id.trim() || null,
        is_active: form.is_active,
      });
      setOpen(false);
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update customer');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Pencil className="mr-2 h-4 w-4" />
          Edit
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit customer</DialogTitle>
          <DialogDescription>Update profile details for {profile.full_name}.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="edit-phone">Phone (E.164)</Label>
            <Input
              id="edit-phone"
              required
              value={form.phone_e164}
              onChange={(e) => setForm((f) => ({ ...f, phone_e164: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-name">Full name</Label>
            <Input
              id="edit-name"
              required
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-email">Email</Label>
            <Input
              id="edit-email"
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
          <div className="space-y-2">
            <Label htmlFor="edit-external">External CRM ID</Label>
            <Input
              id="edit-external"
              value={form.external_crm_id}
              onChange={(e) => setForm((f) => ({ ...f, external_crm_id: e.target.value }))}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Active</p>
              <p className="text-xs text-muted-foreground">Inactive customers are hidden from campaigns.</p>
            </div>
            <Switch
              checked={form.is_active}
              onCheckedChange={(checked) => setForm((f) => ({ ...f, is_active: checked }))}
            />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving…' : 'Save changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
