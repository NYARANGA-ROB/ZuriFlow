/** Client for the self-serve agent wizard API. */

export type IndustryOption = {
    industry_id: string;
    name: string;
    description: string;
    icon: string;
    recommended_template_id: string | null;
    template_name: string | null;
    supported_locales: string[];
    supports_mpesa: boolean;
    default_locale: string;
    example_use_cases: string[];
    business_type?: string;
};

export type VoiceOption = {
    voice_id: string;
    label: string;
    provider?: string;
    language?: string;
};

export type LocaleOption = {
    code: string;
    label: string;
    flag: string;
};

export type TelephonyConfigOption = {
    id: number;
    name: string;
    provider: string;
};

export type WizardCatalog = {
    industries: IndustryOption[];
    voices: VoiceOption[];
    locales: LocaleOption[];
    personalities?: { id: string; label: string }[];
    telephony_configs: TelephonyConfigOption[];
};

export type WizardSession = {
    session_uuid: string;
    organization_id: number;
    state: string;
    progress_percent: number;
    config: Record<string, unknown>;
    workflow_id: number | null;
    phone_number_id: number | null;
    error_message: string | null;
    completed_at: string | null;
    deployment?: {
        workflow_id: number;
        workflow_name: string;
        phone_number_id: number | null;
    };
};

async function wizardFetch<T>(
    baseUrl: string,
    token: string,
    path: string,
    init?: RequestInit,
): Promise<T> {
    const res = await fetch(`${baseUrl}/api/v1/agent-wizard${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            ...(init?.headers ?? {}),
        },
    });
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = body.detail;
        const message =
            typeof detail === 'string'
                ? detail
                : detail?.errors?.join?.(', ') ?? `Request failed (${res.status})`;
        throw new Error(message);
    }
    if (res.status === 204) {
        return undefined as T;
    }
    return res.json() as Promise<T>;
}

export async function fetchWizardCatalog(baseUrl: string, token: string): Promise<WizardCatalog> {
    return wizardFetch(baseUrl, token, '/catalog');
}

export async function startWizardSession(baseUrl: string, token: string): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, '/sessions', { method: 'POST' });
}

export async function saveWizardIndustry(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    industry: { industry_id: string; template_id?: string | null },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/industry`, {
        method: 'POST',
        body: JSON.stringify({ industry: { ...industry, template_source: 'vertical' } }),
    });
}

export async function saveWizardWorkflow(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    workflow: {
        agent_name: string;
        call_direction: 'inbound' | 'outbound';
        use_case: string;
        activity_description: string;
    },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/workflow`, {
        method: 'POST',
        body: JSON.stringify({ workflow }),
    });
}

export async function saveWizardLanguage(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    locale: {
        primary_locale: string;
        kenyan_language_mode: 'english' | 'swahili' | 'mixed' | 'sheng';
    },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/language`, {
        method: 'POST',
        body: JSON.stringify({ locale }),
    });
}

export async function saveWizardPayments(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    payments: {
        enable_mpesa: boolean;
        enable_sms: boolean;
        enable_whatsapp: boolean;
        currency: string;
    },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/payments`, {
        method: 'POST',
        body: JSON.stringify({ payments }),
    });
}

export async function saveWizardCrm(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    crm: { enable_crm: boolean; enable_timeline: boolean; enable_analytics: boolean },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/crm`, {
        method: 'POST',
        body: JSON.stringify({ crm }),
    });
}

export async function saveWizardEscalation(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    escalation: { enable_human_escalation: boolean; after_hours_escalate: boolean; notes: string },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/escalation`, {
        method: 'POST',
        body: JSON.stringify({ escalation }),
    });
}

export async function saveWizardVoice(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    voice: { voice_id: string; speed: number },
    personality?: { style: string },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/voice`, {
        method: 'POST',
        body: JSON.stringify({
            voice: { ...voice, provider: 'dograh', language: 'multi' },
            personality: personality ?? { style: 'friendly' },
        }),
    });
}

export async function saveWizardBusinessHours(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    business_hours: { timezone: string },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/business-hours`, {
        method: 'POST',
        body: JSON.stringify({ business_hours }),
    });
}

export async function saveWizardPhone(
    baseUrl: string,
    token: string,
    sessionUuid: string,
    phone: {
        telephony_configuration_id: number | null;
        address: string | null;
        country_code: string;
        skip_assignment: boolean;
    },
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/phone`, {
        method: 'POST',
        body: JSON.stringify({ phone }),
    });
}

export async function deployWizardAgent(
    baseUrl: string,
    token: string,
    sessionUuid: string,
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/deploy`, { method: 'POST' });
}

export async function advanceWizardSession(
    baseUrl: string,
    token: string,
    sessionUuid: string,
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/advance`, { method: 'POST' });
}

export async function backWizardSession(
    baseUrl: string,
    token: string,
    sessionUuid: string,
): Promise<WizardSession> {
    return wizardFetch(baseUrl, token, `/sessions/${sessionUuid}/back`, { method: 'POST' });
}
