'use client';

import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  type KenyaAnalyticsSnapshot,
  type KenyaPhrase,
  createKenyaPhrase,
  fetchKenyaAnalytics,
  fetchKenyaPhrases,
} from '@/lib/kenyaIntelligenceApi';

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function KenyaIntelligencePage() {
  const { isAuthenticated } = useAuth();
  const [analytics, setAnalytics] = useState<KenyaAnalyticsSnapshot | null>(null);
  const [phrases, setPhrases] = useState<KenyaPhrase[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [phrase, setPhrase] = useState('');
  const [meaning, setMeaning] = useState('');
  const [language, setLanguage] = useState('sheng');
  const [region, setRegion] = useState('national');

  const load = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const [snap, dict] = await Promise.all([fetchKenyaAnalytics(), fetchKenyaPhrases()]);
      setAnalytics(snap);
      setPhrases([...dict.admin_phrases, ...dict.file_phrases.slice(0, 40)]);
      setError(null);
    } catch {
      setError('Unable to load Kenya intelligence data.');
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void load();
  }, [load]);

  const onSave = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await createKenyaPhrase({ phrase, meaning, language, region });
      setPhrase('');
      setMeaning('');
      await load();
    } catch {
      setError('Could not save phrase. Check you are signed in to an organization.');
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Kenya conversational intelligence</h1>
        <p className="text-sm text-muted-foreground">
          Language mix, Sheng usage, confidence, and the editable phrase catalog. Rates are
          estimates with per-turn confidence — not a claim of perfect understanding.
        </p>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <Metric title="Turns" value={String(analytics?.turns ?? 0)} />
        <Metric title="Sheng usage" value={pct(analytics?.sheng_usage_rate ?? 0)} />
        <Metric title="Code-switch rate" value={pct(analytics?.code_switching_rate ?? 0)} />
        <Metric title="Clarification rate" value={pct(analytics?.clarification_rate ?? 0)} />
        <Metric title="Failed recognition" value={pct(analytics?.failed_recognition_rate ?? 0)} />
        <Metric title="Escalation rate" value={pct(analytics?.escalation_rate ?? 0)} />
        <Metric title="Intent success" value={pct(analytics?.successful_intent_rate ?? 0)} />
        <Metric
          title="Languages seen"
          value={Object.keys(analytics?.language_distribution ?? {}).join(', ') || '—'}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add a regional phrase</CardTitle>
          <CardDescription>
            Sheng is not one vocabulary. Tag region and language so matches stay contextual.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={onSave}>
            <div className="space-y-1">
              <Label htmlFor="phrase">Phrase</Label>
              <Input id="phrase" value={phrase} onChange={(e) => setPhrase(e.target.value)} required />
            </div>
            <div className="space-y-1">
              <Label htmlFor="meaning">Meaning</Label>
              <Input id="meaning" value={meaning} onChange={(e) => setMeaning(e.target.value)} required />
            </div>
            <div className="space-y-1">
              <Label htmlFor="language">Language</Label>
              <Input id="language" value={language} onChange={(e) => setLanguage(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="region">Region</Label>
              <Input id="region" value={region} onChange={(e) => setRegion(e.target.value)} />
            </div>
            <div className="md:col-span-2">
              <Button type="submit">Save phrase</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Phrase catalog</CardTitle>
          <CardDescription>Active file dictionary plus organization overlays.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Phrase</TableHead>
                <TableHead>Meaning</TableHead>
                <TableHead>Language</TableHead>
                <TableHead>Region</TableHead>
                <TableHead>Intent</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {phrases.map((row) => (
                <TableRow key={`${row.id ?? row.phrase}-${row.region}`}>
                  <TableCell>{row.phrase}</TableCell>
                  <TableCell>{row.meaning}</TableCell>
                  <TableCell>{row.language}</TableCell>
                  <TableCell>{row.region}</TableCell>
                  <TableCell>{row.intent ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="text-2xl font-semibold">{value}</CardContent>
    </Card>
  );
}
