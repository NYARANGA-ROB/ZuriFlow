export function buildLiveDashboardWsUrl(
  baseUrl: string,
  token: string,
  days = 1,
): string {
  const wsBase = baseUrl.replace(/^http/, 'ws');
  return `${wsBase}/api/v1/admin-operations/ws/live?days=${days}&token=${encodeURIComponent(token)}`;
}
