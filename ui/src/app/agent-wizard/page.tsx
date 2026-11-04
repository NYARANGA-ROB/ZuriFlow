'use client';

import {
    Bed,
    Building2,
    Bus,
    Car,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    GraduationCap,
    Headset,
    HeartPulse,
    Landmark,
    Loader2,
    Package,
    Pill,
    Plane,
    School,
    Shield,
    Sprout,
    Store,
    Truck,
    Utensils,
    Wallet,
    Wrench,
    Zap,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useAppConfig } from '@/context/AppConfigContext';
import { useAuth } from '@/lib/auth';
import {
    advanceWizardSession,
    backWizardSession,
    deployWizardAgent,
    fetchWizardCatalog,
    IndustryOption,
    saveWizardBusinessHours,
    saveWizardCrm,
    saveWizardEscalation,
    saveWizardIndustry,
    saveWizardLanguage,
    saveWizardPayments,
    saveWizardPhone,
    saveWizardVoice,
    saveWizardWorkflow,
    startWizardSession,
    WizardCatalog,
    WizardSession,
} from '@/lib/agentWizardApi';
import logger from '@/lib/logger';

const STEPS = [
    { id: 'industry', label: 'Industry' },
    { id: 'workflow', label: 'Your business' },
    { id: 'language', label: 'Languages' },
    { id: 'payments', label: 'Payments' },
    { id: 'crm', label: 'Customer records' },
    { id: 'escalation', label: 'Human help' },
    { id: 'voice', label: 'Personality' },
    { id: 'business_hours', label: 'Hours' },
    { id: 'phone', label: 'Advanced' },
    { id: 'website', label: 'Website' },
    { id: 'knowledge_sources', label: 'Documents' },
    { id: 'integrations', label: 'Connected systems' },
    { id: 'review_discovered', label: 'Review findings' },
    { id: 'test_agent', label: 'Test' },
    { id: 'review', label: 'Preview & publish' },
] as const;

type StepId = (typeof STEPS)[number]['id'];

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
    wallet: Wallet,
    store: Store,
    'heart-pulse': HeartPulse,
    bed: Bed,
    headset: Headset,
    landmark: Landmark,
    pill: Pill,
    school: School,
    'graduation-cap': GraduationCap,
    home: Building2,
    'building-2': Building2,
    utensils: Utensils,
    truck: Truck,
    package: Package,
    bus: Bus,
    car: Car,
    wrench: Wrench,
    plane: Plane,
    sprout: Sprout,
    'heart-handshake': Headset,
    zap: Zap,
    shield: Shield,
    building: Building2,
};

function stepIndex(state: string): number {
    const map: Record<string, number> = {
        industry: 0,
        workflow: 1,
        language: 2,
        payments: 3,
        crm: 4,
        escalation: 5,
        voice: 6,
        business_hours: 7,
        phone: 8,
        review: 9,
        deploying: 9,
        completed: 9,
    };
    return map[state] ?? 0;
}

export default function AgentWizardPage() {
    const router = useRouter();
    const { user, getAccessToken } = useAuth();
    const { config: appConfig } = useAppConfig();

    const [catalog, setCatalog] = useState<WizardCatalog | null>(null);
    const [session, setSession] = useState<WizardSession | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showAdvanced, setShowAdvanced] = useState(false);

    const [selectedIndustry, setSelectedIndustry] = useState<string>('');
    const [agentName, setAgentName] = useState('');
    const [callDirection, setCallDirection] = useState<'inbound' | 'outbound'>('inbound');
    const [useCase, setUseCase] = useState('');
    const [activityDescription, setActivityDescription] = useState('');
    const [primaryLocale, setPrimaryLocale] = useState('mixed');
    const [enableMpesa, setEnableMpesa] = useState(false);
    const [enableSms, setEnableSms] = useState(true);
    const [enableWhatsapp, setEnableWhatsapp] = useState(true);
    const [enableCrm, setEnableCrm] = useState(true);
    const [enableTimeline, setEnableTimeline] = useState(true);
    const [enableAnalytics, setEnableAnalytics] = useState(true);
    const [enableEscalation, setEnableEscalation] = useState(true);
    const [afterHoursEscalate, setAfterHoursEscalate] = useState(true);
    const [personality, setPersonality] = useState('friendly');
    const [voiceId, setVoiceId] = useState('default');
    const [timezone, setTimezone] = useState('Africa/Nairobi');
    const [telephonyConfigId, setTelephonyConfigId] = useState<string>('');
    const [phoneAddress, setPhoneAddress] = useState('');
    const [skipPhone, setSkipPhone] = useState(true);

    const backendUrl = appConfig?.backendUrl ?? process.env.NEXT_PUBLIC_BACKEND_URL ?? '';
    const currentStep = stepIndex(session?.state ?? 'industry');
    const progress = session?.progress_percent ?? 0;
    const stepId: StepId = STEPS[currentStep]?.id ?? 'industry';

    const industryMeta = useMemo(
        () => catalog?.industries.find((i) => i.industry_id === selectedIndustry),
        [catalog, selectedIndustry],
    );

    const init = useCallback(async () => {
        if (!user || !backendUrl || backendUrl === 'unknown') return;
        setLoading(true);
        setError(null);
        try {
            const token = await getAccessToken();
            const [cat, sess] = await Promise.all([
                fetchWizardCatalog(backendUrl, token),
                startWizardSession(backendUrl, token),
            ]);
            setCatalog(cat);
            setSession(sess);
        } catch (err) {
            setError('Could not start setup. Please try again.');
            logger.error(`Agent wizard init failed: ${err}`);
        } finally {
            setLoading(false);
        }
    }, [user, backendUrl, getAccessToken]);

    useEffect(() => {
        void init();
    }, [init]);

    const handleIndustrySelect = (industry: IndustryOption) => {
        setSelectedIndustry(industry.industry_id);
        if (!useCase && industry.example_use_cases[0]) {
            setUseCase(industry.example_use_cases[0]);
        }
        if (!agentName) {
            setAgentName(`${industry.name} line`);
        }
        setPrimaryLocale(industry.default_locale);
        setEnableMpesa(industry.supports_mpesa);
        if (industry.example_use_cases.length) {
            setActivityDescription(
                `Help callers with: ${industry.example_use_cases.join(', ')}. Speak clearly in English or Kiswahili.`,
            );
        }
    };

    const languageMode = (): 'english' | 'swahili' | 'mixed' | 'sheng' => {
        if (primaryLocale === 'sw') return 'swahili';
        if (primaryLocale === 'en') return 'english';
        if (primaryLocale === 'sheng') return 'sheng';
        return 'mixed';
    };

    const saveCurrentStep = async (): Promise<WizardSession | null> => {
        if (!session || !backendUrl) return null;
        const token = await getAccessToken();
        setSaving(true);
        setError(null);
        try {
            let updated: WizardSession;
            switch (stepId) {
                case 'industry':
                    updated = await saveWizardIndustry(backendUrl, token, session.session_uuid, {
                        industry_id: selectedIndustry,
                        template_id: industryMeta?.recommended_template_id,
                    });
                    break;
                case 'workflow':
                    updated = await saveWizardWorkflow(backendUrl, token, session.session_uuid, {
                        agent_name: agentName,
                        call_direction: callDirection,
                        use_case: useCase,
                        activity_description: activityDescription,
                    });
                    break;
                case 'language':
                    updated = await saveWizardLanguage(backendUrl, token, session.session_uuid, {
                        primary_locale: primaryLocale,
                        kenyan_language_mode: languageMode(),
                    });
                    break;
                case 'payments':
                    updated = await saveWizardPayments(backendUrl, token, session.session_uuid, {
                        enable_mpesa: enableMpesa,
                        enable_sms: enableSms,
                        enable_whatsapp: enableWhatsapp,
                        currency: 'KES',
                    });
                    break;
                case 'crm':
                    updated = await saveWizardCrm(backendUrl, token, session.session_uuid, {
                        enable_crm: enableCrm,
                        enable_timeline: enableTimeline,
                        enable_analytics: enableAnalytics,
                    });
                    break;
                case 'escalation':
                    updated = await saveWizardEscalation(backendUrl, token, session.session_uuid, {
                        enable_human_escalation: enableEscalation,
                        after_hours_escalate: afterHoursEscalate,
                        notes: '',
                    });
                    break;
                case 'voice':
                    updated = await saveWizardVoice(
                        backendUrl,
                        token,
                        session.session_uuid,
                        { voice_id: voiceId, speed: 1.0 },
                        { style: personality },
                    );
                    break;
                case 'business_hours':
                    updated = await saveWizardBusinessHours(backendUrl, token, session.session_uuid, {
                        timezone,
                    });
                    break;
                case 'phone':
                    updated = await saveWizardPhone(backendUrl, token, session.session_uuid, {
                        telephony_configuration_id: telephonyConfigId
                            ? Number(telephonyConfigId)
                            : null,
                        address: phoneAddress || null,
                        country_code: 'KE',
                        skip_assignment: skipPhone,
                    });
                    break;
                case 'review':
                    updated = await deployWizardAgent(backendUrl, token, session.session_uuid);
                    break;
                default:
                    updated = session;
                    break;
            }
            if (stepId !== 'review') {
                updated = await advanceWizardSession(backendUrl, token, updated.session_uuid);
            }
            setSession(updated);
            return updated;
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Something went wrong');
            return null;
        } finally {
            setSaving(false);
        }
    };

    const handleNext = async () => {
        const updated = await saveCurrentStep();
        if (updated?.state === 'completed' && updated.deployment?.workflow_id) {
            router.push(`/workflow/${updated.deployment.workflow_id}?onboarding=web_call`);
        }
    };

    const handleBack = async () => {
        if (!session || !backendUrl || currentStep === 0) return;
        setSaving(true);
        try {
            const token = await getAccessToken();
            const updated = await backWizardSession(backendUrl, token, session.session_uuid);
            setSession(updated);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not go back');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-b from-emerald-50/80 to-background dark:from-background">
            <div className="container mx-auto px-4 py-8 max-w-4xl">
                <div className="mb-8">
                    <Badge variant="secondary" className="mb-3">
                        Kenya · about 8 minutes
                    </Badge>
                    <h1 className="text-3xl font-bold mb-2">Launch a voice agent for your business</h1>
                    <p className="text-muted-foreground">
                        Pick your industry, answer a few questions, and go live. Karibu — no technical
                        setup required.
                    </p>
                    <Progress value={progress} className="mt-4 h-2" />
                    <div className="flex flex-wrap gap-2 mt-3">
                        {STEPS.map((step, idx) => (
                            <Badge
                                key={step.id}
                                variant={
                                    idx === currentStep
                                        ? 'default'
                                        : idx < currentStep
                                          ? 'secondary'
                                          : 'outline'
                                }
                            >
                                {step.label}
                            </Badge>
                        ))}
                    </div>
                </div>

                {error && (
                    <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                        {error}
                    </div>
                )}

                <Card>
                    <CardHeader>
                        <CardTitle>{STEPS[currentStep]?.label ?? 'Setup'}</CardTitle>
                        <CardDescription>
                            Step {currentStep + 1} of {STEPS.length}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {stepId === 'industry' && catalog && (
                            <div className="grid gap-3 sm:grid-cols-2">
                                {catalog.industries.map((industry) => {
                                    const Icon = ICONS[industry.icon] ?? Headset;
                                    const selected = selectedIndustry === industry.industry_id;
                                    return (
                                        <button
                                            key={industry.industry_id}
                                            type="button"
                                            onClick={() => handleIndustrySelect(industry)}
                                            className={`text-left rounded-lg border p-4 transition hover:border-primary ${
                                                selected ? 'border-primary bg-primary/5' : ''
                                            }`}
                                        >
                                            <div className="flex items-start gap-3">
                                                <Icon className="h-5 w-5 mt-0.5 shrink-0" />
                                                <div>
                                                    <p className="font-medium">{industry.name}</p>
                                                    <p className="text-sm text-muted-foreground mt-1">
                                                        {industry.description}
                                                    </p>
                                                    {industry.supports_mpesa && (
                                                        <Badge variant="outline" className="mt-2">
                                                            M-Pesa
                                                        </Badge>
                                                    )}
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}

                        {stepId === 'workflow' && (
                            <>
                                <p className="text-sm text-muted-foreground">
                                    {industryMeta?.business_type
                                        ? `We will tailor the agent for ${industryMeta.business_type.toLowerCase()}s.`
                                        : 'Tell us what this line should do.'}
                                </p>
                                <div className="space-y-2">
                                    <Label htmlFor="agent-name">What should callers hear as the name?</Label>
                                    <Input
                                        id="agent-name"
                                        value={agentName}
                                        onChange={(e) => setAgentName(e.target.value)}
                                        placeholder="e.g. Stima Sacco member line"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>How will people reach you?</Label>
                                    <RadioGroup
                                        value={callDirection}
                                        onValueChange={(v) =>
                                            setCallDirection(v as 'inbound' | 'outbound')
                                        }
                                    >
                                        <div className="flex items-center space-x-2">
                                            <RadioGroupItem value="inbound" id="inbound" />
                                            <Label htmlFor="inbound">Customers call you</Label>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <RadioGroupItem value="outbound" id="outbound" />
                                            <Label htmlFor="outbound">You call customers</Label>
                                        </div>
                                    </RadioGroup>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="use-case">Main goal</Label>
                                    <Input
                                        id="use-case"
                                        value={useCase}
                                        onChange={(e) => setUseCase(e.target.value)}
                                        placeholder="e.g. Answer fee questions"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="description">In simple words, what should it handle?</Label>
                                    <Textarea
                                        id="description"
                                        value={activityDescription}
                                        onChange={(e) => setActivityDescription(e.target.value)}
                                        rows={4}
                                    />
                                </div>
                            </>
                        )}

                        {stepId === 'language' && catalog && (
                            <div className="space-y-2">
                                <Label>Which languages should the agent use?</Label>
                                <Select value={primaryLocale} onValueChange={setPrimaryLocale}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {catalog.locales.map((loc) => (
                                            <SelectItem key={loc.code} value={loc.code}>
                                                {loc.flag} {loc.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <p className="text-sm text-muted-foreground">
                                    The agent can greet in English or Kiswahili and follow the customer.
                                </p>
                            </div>
                        )}

                        {stepId === 'payments' && (
                            <div className="space-y-3">
                                <p className="text-sm text-muted-foreground">
                                    Optional. Amounts are treated as Kenyan Shillings (KES).
                                </p>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={enableMpesa}
                                        onChange={(e) => setEnableMpesa(e.target.checked)}
                                    />
                                    Collect or confirm M-Pesa payments
                                </label>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={enableSms}
                                        onChange={(e) => setEnableSms(e.target.checked)}
                                    />
                                    Send SMS follow-ups
                                </label>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={enableWhatsapp}
                                        onChange={(e) => setEnableWhatsapp(e.target.checked)}
                                    />
                                    Send WhatsApp follow-ups
                                </label>
                            </div>
                        )}

                        {stepId === 'crm' && (
                            <div className="space-y-3">
                                <p className="text-sm text-muted-foreground">
                                    Keep a record of who called and what was agreed.
                                </p>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={enableCrm}
                                        onChange={(e) => setEnableCrm(e.target.checked)}
                                    />
                                    Save customers (Kenyan phone numbers)
                                </label>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={enableTimeline}
                                        onChange={(e) => setEnableTimeline(e.target.checked)}
                                    />
                                    Call timeline on the customer record
                                </label>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={enableAnalytics}
                                        onChange={(e) => setEnableAnalytics(e.target.checked)}
                                    />
                                    Simple call analytics
                                </label>
                            </div>
                        )}

                        {stepId === 'escalation' && (
                            <div className="space-y-3">
                                <p className="text-sm text-muted-foreground">
                                    When should a person take over?
                                </p>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={enableEscalation}
                                        onChange={(e) => setEnableEscalation(e.target.checked)}
                                    />
                                    Transfer to a person when the caller asks, or the request is sensitive
                                </label>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={afterHoursEscalate}
                                        onChange={(e) => setAfterHoursEscalate(e.target.checked)}
                                    />
                                    Take a message after Kenyan business hours and public holidays
                                </label>
                            </div>
                        )}

                        {stepId === 'voice' && catalog && (
                            <>
                                <div className="space-y-2">
                                    <Label>How should the agent sound?</Label>
                                    <Select value={personality} onValueChange={setPersonality}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {(catalog.personalities ?? []).map((p) => (
                                                <SelectItem key={p.id} value={p.id}>
                                                    {p.label}
                                                </SelectItem>
                                            ))}
                                            {(!catalog.personalities ||
                                                catalog.personalities.length === 0) && (
                                                <SelectItem value="friendly">Friendly</SelectItem>
                                            )}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Voice</Label>
                                    <Select value={voiceId} onValueChange={setVoiceId}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {catalog.voices.map((v) => (
                                                <SelectItem key={v.voice_id} value={v.voice_id}>
                                                    {v.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </>
                        )}

                        {stepId === 'business_hours' && (
                            <div className="space-y-2">
                                <Label>When are you open? (East Africa Time)</Label>
                                <Select value={timezone} onValueChange={setTimezone}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="Africa/Nairobi">
                                            Kenya — Nairobi time
                                        </SelectItem>
                                    </SelectContent>
                                </Select>
                                <p className="text-sm text-muted-foreground">
                                    Default: Monday to Friday, 8:00am–5:00pm. Kenyan public holidays are
                                    treated as closed unless you change this later.
                                </p>
                            </div>
                        )}

                        {stepId === 'phone' && catalog && (
                            <>
                                <p className="text-sm text-muted-foreground">
                                    You can publish now and add a phone number later. Leave this skipped
                                    unless you already have a Kenya number connected.
                                </p>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={skipPhone}
                                        onChange={(e) => setSkipPhone(e.target.checked)}
                                    />
                                    Skip phone for now (recommended)
                                </label>
                                <button
                                    type="button"
                                    className="flex items-center text-sm text-muted-foreground"
                                    onClick={() => setShowAdvanced((v) => !v)}
                                >
                                    <ChevronDown className="h-4 w-4 mr-1" />
                                    Advanced settings
                                </button>
                                {showAdvanced && !skipPhone && (
                                    <>
                                        <div className="space-y-2">
                                            <Label>Phone connection</Label>
                                            <Select
                                                value={telephonyConfigId}
                                                onValueChange={setTelephonyConfigId}
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select if you already set this up" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {catalog.telephony_configs.length === 0 ? (
                                                        <SelectItem value="none" disabled>
                                                            None yet — skip and add later
                                                        </SelectItem>
                                                    ) : (
                                                        catalog.telephony_configs.map((c) => (
                                                            <SelectItem key={c.id} value={String(c.id)}>
                                                                {c.name}
                                                            </SelectItem>
                                                        ))
                                                    )}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="phone">Kenya phone number</Label>
                                            <Input
                                                id="phone"
                                                value={phoneAddress}
                                                onChange={(e) => setPhoneAddress(e.target.value)}
                                                placeholder="0712 345 678 or +254712345678"
                                            />
                                        </div>
                                    </>
                                )}
                            </>
                        )}

                        {stepId === 'website' && (
                            <div className="space-y-3">
                                <p className="text-sm text-muted-foreground">
                                    Add your website if you have one. ZuriFlow will read public pages such as
                                    About, Services, and Contact. You will approve anything it finds.
                                </p>
                                <p className="text-sm">You can skip this and import later from Business Information.</p>
                            </div>
                        )}
                        {stepId === 'knowledge_sources' && (
                            <p className="text-sm text-muted-foreground">
                                Upload price lists, menus, or policies from Business Information after you
                                publish. Nothing is used until you approve it.
                            </p>
                        )}
                        {stepId === 'integrations' && (
                            <p className="text-sm text-muted-foreground">
                                Connect stock, bookings, or M-Pesa so the agent answers from live systems
                                instead of old documents.
                            </p>
                        )}
                        {stepId === 'review_discovered' && (
                            <p className="text-sm text-muted-foreground">
                                Open Latest Changes after publishing to approve prices, hours, and policies
                                before customers hear them.
                            </p>
                        )}
                        {stepId === 'test_agent' && (
                            <p className="text-sm text-muted-foreground">
                                After publish you can place a Web Call and ask: opening hours, stock, booking,
                                and M-Pesa.
                            </p>
                        )}

                        {stepId === 'review' && (
                            <div className="space-y-3 text-sm">
                                <p>
                                    <strong>Industry:</strong> {industryMeta?.name ?? selectedIndustry}
                                </p>
                                <p>
                                    <strong>Agent:</strong> {agentName}
                                </p>
                                <p>
                                    <strong>Languages:</strong> {primaryLocale}
                                </p>
                                <p>
                                    <strong>M-Pesa:</strong> {enableMpesa ? 'Yes' : 'No'} ·{' '}
                                    <strong>WhatsApp:</strong> {enableWhatsapp ? 'Yes' : 'No'} ·{' '}
                                    <strong>SMS:</strong> {enableSms ? 'Yes' : 'No'}
                                </p>
                                <p>
                                    <strong>Customer records & analytics:</strong>{' '}
                                    {enableCrm ? 'On' : 'Off'}
                                </p>
                                <p className="text-muted-foreground pt-2">
                                    We will generate a ready-made conversation: greeting, language,
                                    identification, FAQs, data collection, tools, escalation, and a call
                                    summary. Publish, then try a test call from the next screen.
                                </p>
                            </div>
                        )}

                        <div className="flex justify-between pt-4">
                            <Button
                                variant="outline"
                                onClick={() => void handleBack()}
                                disabled={currentStep === 0 || saving}
                            >
                                <ChevronLeft className="h-4 w-4 mr-1" />
                                Back
                            </Button>
                            <Button
                                onClick={() => void handleNext()}
                                disabled={saving || (stepId === 'industry' && !selectedIndustry)}
                            >
                                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                {stepId === 'review' ? 'Publish and try a test call' : 'Continue'}
                                {stepId !== 'review' && <ChevronRight className="h-4 w-4 ml-1" />}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
