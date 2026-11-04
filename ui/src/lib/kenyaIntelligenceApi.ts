import { client } from '@/client/client.gen';

export interface KenyaAnalyticsSnapshot {
  turns: number;
  language_distribution: Record<string, number>;
  sheng_usage_rate: number;
  code_switching_rate: number;
  failed_recognition_rate: number;
  clarification_rate: number;
  escalation_rate: number;
  successful_intent_rate: number;
  language_specific_completion: Record<string, number>;
  mix_distribution: Record<string, number>;
}

export interface KenyaPhrase {
  id?: number;
  phrase: string;
  meaning: string;
  language: string;
  intent?: string | null;
  confidence: number;
  context?: string | null;
  region: string;
  version: string;
  active: boolean;
  organization_id?: number | null;
}

export async function fetchKenyaAnalytics(): Promise<KenyaAnalyticsSnapshot> {
  const response = await client.get({ url: '/api/v1/kenya/analytics' });
  if (response.error || !response.data) {
    return {
      turns: 0,
      language_distribution: {},
      sheng_usage_rate: 0,
      code_switching_rate: 0,
      failed_recognition_rate: 0,
      clarification_rate: 0,
      escalation_rate: 0,
      successful_intent_rate: 0,
      language_specific_completion: {},
      mix_distribution: {},
    };
  }
  return response.data as KenyaAnalyticsSnapshot;
}

export async function fetchKenyaPhrases(): Promise<{
  file_phrases: KenyaPhrase[];
  admin_phrases: KenyaPhrase[];
}> {
  const response = await client.get({ url: '/api/v1/kenya/phrases' });
  if (response.error || !response.data) {
    return { file_phrases: [], admin_phrases: [] };
  }
  return response.data as { file_phrases: KenyaPhrase[]; admin_phrases: KenyaPhrase[] };
}

export async function createKenyaPhrase(body: {
  phrase: string;
  meaning: string;
  language: string;
  intent?: string;
  region?: string;
  context?: string;
}): Promise<KenyaPhrase> {
  const response = await client.post({
    url: '/api/v1/kenya/phrases',
    body,
  });
  if (response.error || !response.data) {
    throw new Error('Unable to save phrase');
  }
  return response.data as KenyaPhrase;
}
