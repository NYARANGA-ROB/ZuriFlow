'use client';

import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/lib/auth';
import { fetchSetup, saveSetup, type SetupProfile } from '@/lib/controlPlaneApi';

export default function OrganizationSetupPage() {
  const { isAuthenticated, redirectToLogin, loading } = useAuth();
  const [profile, setProfile] = useState<SetupProfile>({});
  const [counties, setCounties] = useState<string[]>([]);
  const [industries, setIndustries] = useState<string[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const load = useCallback(async () => {
    const data = await fetchSetup();
    setProfile(data.profile);
    setCounties(data.counties);
    setIndustries(data.industries);
    setReady(data.completeness.ready);
  }, []);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      redirectToLogin();
    }
  }, [isAuthenticated, loading, redirectToLogin]);

  useEffect(() => {
    if (isAuthenticated) {
      load().catch(() => setStatus('Could not load setup.'));
    }
  }, [isAuthenticated, load]);

  const update = (patch: Partial<SetupProfile>) => setProfile((prev) => ({ ...prev, ...patch }));

  const onSave = async () => {
    try {
      const result = await saveSetup(profile);
      setReady(result.completeness.ready);
      setStatus('Saved. Your agents will use this business profile.');
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Save failed');
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 py-10 px-4">
      <div>
        <h1 className="text-2xl font-bold">Organization setup</h1>
        <p className="text-muted-foreground">
          Tell us about the business. We will run a Kenyan AI receptionist on voice, WhatsApp, and M-Pesa.
          Import your website and documents from Business Information after this.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Business</CardTitle>
          <CardDescription>
            {ready ? 'Setup is complete.' : 'Finish every section before going live.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="business_name">Business name</Label>
            <Input
              id="business_name"
              value={profile.business_name ?? ''}
              onChange={(e) => update({ business_name: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="industry">Industry</Label>
            <Input
              id="industry"
              list="industries"
              value={profile.industry ?? ''}
              onChange={(e) => update({ industry: e.target.value })}
            />
            <datalist id="industries">
              {industries.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>
          <div>
            <Label htmlFor="location">Location</Label>
            <Input
              id="location"
              value={profile.location ?? ''}
              onChange={(e) => update({ location: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="county">County</Label>
            <Input
              id="county"
              list="counties"
              value={profile.county ?? ''}
              onChange={(e) => update({ county: e.target.value })}
            />
            <datalist id="counties">
              {counties.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>
          <div>
            <Label htmlFor="hours">Business hours</Label>
            <Input
              id="hours"
              value={profile.business_hours?.weekdays ?? '08:00-17:00'}
              onChange={(e) =>
                update({
                  business_hours: {
                    timezone: 'Africa/Nairobi',
                    weekdays: e.target.value,
                    saturday: profile.business_hours?.saturday ?? null,
                    sunday: profile.business_hours?.sunday ?? null,
                  },
                })
              }
            />
          </div>
          <div>
            <Label htmlFor="phone">Main phone number</Label>
            <Input
              id="phone"
              value={profile.phone_numbers?.[0]?.number ?? ''}
              onChange={(e) =>
                update({
                  phone_numbers: [{ label: 'main', number: e.target.value, purpose: 'inbound' }],
                })
              }
            />
          </div>
          <div>
            <Label htmlFor="languages">Languages (comma separated)</Label>
            <Input
              id="languages"
              value={(profile.languages ?? []).join(', ')}
              onChange={(e) =>
                update({
                  languages: e.target.value.split(',').map((part) => part.trim()).filter(Boolean),
                })
              }
            />
          </div>
          <div>
            <Label htmlFor="paybill">M-Pesa paybill</Label>
            <Input
              id="paybill"
              value={profile.payment?.paybill ?? ''}
              onChange={(e) =>
                update({
                  payment: {
                    mpesa_enabled: true,
                    paybill: e.target.value,
                    till_number: profile.payment?.till_number ?? null,
                    account_reference: profile.payment?.account_reference ?? null,
                  },
                })
              }
            />
          </div>
          <div>
            <Label htmlFor="escalation">Escalation contact phone</Label>
            <Input
              id="escalation"
              value={profile.escalation_contacts?.[0]?.phone ?? ''}
              onChange={(e) =>
                update({
                  escalation_contacts: [
                    { name: 'Supervisor', phone: e.target.value, role: 'supervisor' },
                  ],
                })
              }
            />
          </div>
          <Button onClick={onSave}>Save setup</Button>
          {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
