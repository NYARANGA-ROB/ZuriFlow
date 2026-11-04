// Smoke tests for analytics, failover UI, and live dashboard wiring.
//
// Run via `npm run test:smoke` from ui/, or:
//   node ui/scripts/test-feature-smoke.mts

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildLiveDashboardWsUrl } from '../src/lib/liveDashboardWs.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));
const UI_ROOT = resolve(__dirname, '..');

function readUi(relativePath: string): string {
  return readFileSync(resolve(UI_ROOT, relativePath), 'utf-8');
}

function assertIncludes(name: string, haystack: string, needle: string) {
  if (!haystack.includes(needle)) {
    console.error(`FAIL ${name}: expected source to include ${JSON.stringify(needle)}`);
    process.exitCode = 1;
    return;
  }
  console.log(`PASS ${name}`);
}

let failed = 0;

function assertEqual(name: string, actual: unknown, expected: unknown) {
  if (actual !== expected) {
    console.error(`FAIL ${name}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    failed++;
    return;
  }
  console.log(`PASS ${name}`);
}

assertEqual(
  'buildLiveDashboardWsUrl uses admin live websocket path',
  buildLiveDashboardWsUrl('https://api.example.com', 'tok en', 1),
  'wss://api.example.com/api/v1/admin-operations/ws/live?days=1&token=tok%20en',
);

assertEqual(
  'buildLiveDashboardWsUrl upgrades http to ws',
  buildLiveDashboardWsUrl('http://localhost:8000', 'abc'),
  'ws://localhost:8000/api/v1/admin-operations/ws/live?days=1&token=abc',
);

const analyticsApi = readUi('src/lib/analyticsApi.ts');
assertIncludes(
  'analyticsApi fetches admin summary',
  analyticsApi,
  "'/api/v1/admin-operations/summary'",
);
assertIncludes(
  'analyticsApi fetches voice dashboard',
  analyticsApi,
  "'/api/v1/voice-analytics/dashboard'",
);
assertIncludes(
  'analyticsApi fetches business metrics',
  analyticsApi,
  "'/api/v1/business-call-analytics/metrics'",
);

const failoverCard = readUi('src/components/telephony/FailoverConfigurationCard.tsx');
assertIncludes(
  'failover card loads configuration',
  failoverCard,
  "'/api/v1/organizations/telephony-failover'",
);
assertIncludes(
  'failover card saves configuration',
  failoverCard,
  "client.put({",
);

const analyticsPage = readUi('src/app/analytics/page.tsx');
assertIncludes('analytics page renders live panel', analyticsPage, 'LiveCallsPanel');
assertIncludes('analytics page uses admin summary', analyticsPage, 'fetchAdminSummary');

const sidebar = readUi('src/components/layout/AppSidebar.tsx');
assertIncludes('sidebar links to analytics', sidebar, '/analytics');

const telephonyPage = readUi('src/app/telephony-configurations/page.tsx');
assertIncludes(
  'telephony page renders failover card',
  telephonyPage,
  'FailoverConfigurationCard',
);

if (failed > 0 || process.exitCode === 1) {
  console.error(`\n${failed} smoke assertion(s) failed`);
  process.exit(1);
}

console.log('\nAll feature smoke checks passed');
