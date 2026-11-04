'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useAuth } from '@/lib/auth';
import {
  createKnowledge,
  fetchKnowledge,
  searchKnowledge,
  type KnowledgeEntry,
} from '@/lib/controlPlaneApi';

export default function KnowledgePage() {
  const { isAuthenticated, redirectToLogin, loading } = useAuth();
  const [categories, setCategories] = useState<string[]>([]);
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [category, setCategory] = useState('faq');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<Array<{ text: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await fetchKnowledge();
    setCategories(data.categories);
    setEntries(data.entries);
  }, []);

  useEffect(() => {
    if (!loading && !isAuthenticated) redirectToLogin();
  }, [isAuthenticated, loading, redirectToLogin]);

  useEffect(() => {
    if (isAuthenticated) {
      load().catch(() => setError('Could not load knowledge.'));
    }
  }, [isAuthenticated, load]);

  const onCreate = async () => {
    try {
      await createKnowledge({ category, title, content });
      setTitle('');
      setContent('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save');
    }
  };

  const onSearch = async () => {
    const result = await searchKnowledge(query);
    setHits(result.results);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 py-10 px-4">
      <div>
        <h1 className="text-2xl font-bold">Business knowledge</h1>
        <p className="text-muted-foreground">
          Agents retrieve matching FAQs, products, and policies. They do not receive the whole
          knowledge base in the prompt.{' '}
          <Link className="underline" href="/files">
            Upload documents
          </Link>
          .
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Add knowledge</CardTitle>
          <CardDescription>Categories: {categories.join(', ')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label htmlFor="category">Category</Label>
            <Input id="category" value={category} onChange={(e) => setCategory(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="content">Content</Label>
            <Textarea id="content" value={content} onChange={(e) => setContent(e.target.value)} />
          </div>
          <Button onClick={onCreate}>Save entry</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Retrieve (test)</CardTitle>
          <CardDescription>See what the agent would pull for a customer question.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask about hours, pricing, a branch..." />
          <Button variant="outline" onClick={onSearch}>
            Search
          </Button>
          {hits.map((hit) => (
            <p key={hit.text} className="text-sm border rounded p-2">
              {hit.text}
            </p>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Entries</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {entries.map((entry) => (
            <div key={entry.id} className="border rounded p-3">
              <p className="text-xs uppercase text-muted-foreground">{entry.category}</p>
              <p className="font-medium">{entry.title}</p>
              <p className="text-sm text-muted-foreground">{entry.content}</p>
            </div>
          ))}
        </CardContent>
      </Card>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
