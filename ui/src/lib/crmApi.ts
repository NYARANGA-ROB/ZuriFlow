import { client } from '@/client/client.gen';

export interface CustomerSummary {
  id: number;
  customer_uuid: string;
  full_name: string;
  phone_e164: string;
  preferred_locale: string;
  is_active: boolean;
}

export interface CustomerProfile extends CustomerSummary {
  organization_id: number;
  email: string | null;
  secondary_locales: string[];
  external_crm_id: string | null;
  total_outstanding: number;
  debt_accounts: Array<Record<string, unknown>>;
  payment_history: Array<Record<string, unknown>>;
  call_history: Array<Record<string, unknown>>;
  escalation_history: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

function extractError(response: { error?: unknown }, fallback: string): string {
  if (typeof response.error === 'object' && response.error !== null && 'detail' in response.error) {
    return String((response.error as { detail?: unknown }).detail);
  }
  return fallback;
}

export async function fetchCrmStatus(): Promise<{ enabled: boolean }> {
  const response = await client.get({ url: '/api/v1/crm/status' });
  if (response.error) {
    return { enabled: false };
  }
  return response.data as { enabled: boolean };
}

export async function listCustomers(params?: {
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<CustomerSummary[]> {
  const response = await client.get({
    url: '/api/v1/crm/customers',
    query: {
      search: params?.search,
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
    },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load customers'));
  }
  return response.data as CustomerSummary[];
}

export async function getCustomerProfile(customerId: number): Promise<CustomerProfile> {
  const response = await client.get({
    url: `/api/v1/crm/customers/${customerId}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Customer not found'));
  }
  return response.data as CustomerProfile;
}

export async function getCustomerByPhone(phoneE164: string): Promise<CustomerProfile> {
  const encoded = encodeURIComponent(phoneE164);
  const response = await client.get({
    url: `/api/v1/crm/customers/by-phone/${encoded}`,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Customer not found'));
  }
  return response.data as CustomerProfile;
}

export interface CreateCustomerInput {
  phone_e164: string;
  full_name: string;
  email?: string | null;
  preferred_locale?: string;
  external_crm_id?: string | null;
  debt_account?: {
    account_reference: string;
    outstanding_balance: number;
    currency?: string;
    days_past_due?: number;
  };
}

export interface UpdateCustomerInput {
  full_name?: string;
  email?: string | null;
  phone_e164?: string;
  preferred_locale?: string;
  external_crm_id?: string | null;
  is_active?: boolean;
}

export async function createCustomer(input: CreateCustomerInput): Promise<CustomerProfile> {
  const response = await client.post({
    url: '/api/v1/crm/customers',
    body: input,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to create customer'));
  }
  return response.data as CustomerProfile;
}

export async function updateCustomer(
  customerId: number,
  input: UpdateCustomerInput,
): Promise<CustomerProfile> {
  const response = await client.patch({
    url: `/api/v1/crm/customers/${customerId}`,
    body: input,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to update customer'));
  }
  return response.data as CustomerProfile;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  resource_type: string;
  resource_id: string | null;
  customer_id: number | null;
  actor_user_id: number | null;
  changes: Record<string, unknown>;
  created_at: string | null;
}

export async function upsertDebtAccount(
  customerId: number,
  input: {
    account_reference: string;
    outstanding_balance: number;
    currency?: string;
    days_past_due?: number;
    minimum_settlement?: number | null;
    status?: string;
  },
): Promise<Record<string, unknown>> {
  const response = await client.put({
    url: `/api/v1/crm/customers/${customerId}/debt`,
    body: input,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to update debt account'));
  }
  return response.data as Record<string, unknown>;
}

export async function recordPayment(
  customerId: number,
  input: {
    amount: number;
    currency?: string;
    payment_method?: string;
    status?: string;
    receipt_reference?: string | null;
  },
): Promise<Record<string, unknown>> {
  const response = await client.post({
    url: `/api/v1/crm/customers/${customerId}/payments`,
    body: input,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to record payment'));
  }
  return response.data as Record<string, unknown>;
}

export async function recordCall(
  customerId: number,
  input: {
    phone_e164: string;
    call_type?: string;
    disposition?: string | null;
    outcome?: string | null;
    summary?: string | null;
    duration_s?: number | null;
  },
): Promise<Record<string, unknown>> {
  const response = await client.post({
    url: `/api/v1/crm/customers/${customerId}/calls`,
    body: input,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to record call'));
  }
  return response.data as Record<string, unknown>;
}

export async function recordEscalation(
  customerId: number,
  input: {
    reason: string;
    risk_level?: string;
    session_id?: string | null;
    queue_name?: string | null;
  },
): Promise<Record<string, unknown>> {
  const response = await client.post({
    url: `/api/v1/crm/customers/${customerId}/escalations`,
    body: input,
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to record escalation'));
  }
  return response.data as Record<string, unknown>;
}

export async function listAuditLogs(params?: {
  customerId?: number;
  limit?: number;
}): Promise<AuditLogEntry[]> {
  const response = await client.get({
    url: '/api/v1/crm/audit-logs',
    query: {
      customer_id: params?.customerId,
      limit: params?.limit ?? 100,
    },
  });
  if (response.error) {
    throw new Error(extractError(response, 'Failed to load audit logs'));
  }
  return response.data as AuditLogEntry[];
}
