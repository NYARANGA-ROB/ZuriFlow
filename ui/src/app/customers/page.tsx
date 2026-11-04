'use client';

import { Phone, Search } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { CreateCustomerDialog } from '@/app/customers/components/CreateCustomerDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuth } from '@/lib/auth';
import {
  type CustomerSummary,
  fetchCrmStatus,
  listCustomers,
} from '@/lib/crmApi';

export default function CustomersPage() {
  const auth = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const phoneFromQuery = searchParams.get('phone');

  const [crmEnabled, setCrmEnabled] = useState<boolean | null>(null);
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const loadCustomers = useCallback(async (query?: string) => {
    setLoading(true);
    setError(null);
    try {
      const rows = await listCustomers({ search: query || undefined, limit: 100 });
      setCustomers(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load customers');
      setCustomers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!auth.isAuthenticated) return;

    const init = async () => {
      const status = await fetchCrmStatus();
      setCrmEnabled(status.enabled);
      if (!status.enabled) {
        setLoading(false);
        return;
      }
      await loadCustomers();
    };

    void init();
  }, [auth.isAuthenticated, loadCustomers]);

  useEffect(() => {
    if (phoneFromQuery) {
      setCreateOpen(true);
    }
  }, [phoneFromQuery]);

  const handleSearch = (event: React.FormEvent) => {
    event.preventDefault();
    void loadCustomers(search.trim() || undefined);
  };

  if (!auth.isAuthenticated) {
    return null;
  }

  if (crmEnabled === false) {
    return (
      <div className="container max-w-4xl py-8">
        <Card>
          <CardHeader>
            <CardTitle>Customers</CardTitle>
            <CardDescription>
              CRM is not enabled on this deployment. Set <code>CRM_ENABLED=true</code> to manage
              customer profiles and timelines.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Customers</h1>
          <p className="text-sm text-muted-foreground">
            Unified CRM profiles with omnichannel voice, WhatsApp, and payment history.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" asChild>
            <Link href="/customers/lookup">
              <Phone className="mr-2 h-4 w-4" />
              Phone lookup
            </Link>
          </Button>
          <CreateCustomerDialog
            initialPhone={phoneFromQuery ?? undefined}
            open={createOpen}
            onOpenChange={setCreateOpen}
            onCreated={(id) => router.push(`/customers/${id}`)}
          />
        </div>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or phone…"
            className="pl-9"
          />
        </div>
        <Button type="submit" variant="secondary">
          Search
        </Button>
        {search.trim().match(/^\+?\d/) ? (
          <Button type="button" variant="outline" asChild>
            <Link href={`/customers/lookup?phone=${encodeURIComponent(search.trim())}`}>
              Timeline
            </Link>
          </Button>
        ) : null}
      </form>

      {error ? (
        <Card className="border-destructive/50">
          <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Customer directory</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : customers.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No customers yet. Profiles are created automatically from voice calls and M-Pesa
              payments, or you can add them via the CRM API.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Locale</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Profile</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {customers.map((customer) => (
                  <TableRow
                    key={customer.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/customers/${customer.id}`)}
                  >
                    <TableCell className="font-medium">{customer.full_name}</TableCell>
                    <TableCell>{customer.phone_e164}</TableCell>
                    <TableCell>{customer.preferred_locale}</TableCell>
                    <TableCell>
                      <Badge variant={customer.is_active ? 'default' : 'secondary'}>
                        {customer.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" asChild>
                        <Link href={`/customers/${customer.id}`}>View</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
