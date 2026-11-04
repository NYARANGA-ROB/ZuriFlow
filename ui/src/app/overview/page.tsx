'use client';

import Link from 'next/link';

import { GitHubStarBadge } from '@/components/layout/GitHubStarBadge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { APP_NAME } from '@/constants/branding';
import { useAuth } from '@/lib/auth';

export default function OverviewPage() {
    const { user, provider } = useAuth();
    const isOSSMode = provider !== 'stack';

    return (
        <div className="container mx-auto px-4 py-8">
            <div className="max-w-4xl mx-auto">
                <Card className="mb-8">
                    <CardHeader>
                        <CardTitle className="text-3xl">
                            {isOSSMode
                                ? `Welcome to ${APP_NAME}`
                                : `Karibu${user?.displayName ? `, ${user.displayName.split(' ')[0]}` : ''}`}
                        </CardTitle>
                        <CardDescription className="text-lg mt-2">
                            Give {APP_NAME} your business details and put a Kenyan AI receptionist
                            on the phone today — Swahili, Sheng, M-Pesa, and WhatsApp included.
                            You do not need to understand the voice pipeline.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {isOSSMode && (
                            <div className="mb-6">
                                <GitHubStarBadge label="Star us on GitHub" showCount source="overview_page" />
                            </div>
                        )}
                        <Button asChild>
                            <Link href="/setup">Set up my receptionist</Link>
                        </Button>
                    </CardContent>
                </Card>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Business setup</CardTitle>
                            <CardDescription>
                                Name, county, hours, languages, and M-Pesa. About five minutes.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Button asChild>
                                <Link href="/setup">Open setup</Link>
                            </Button>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader>
                            <CardTitle>Create the agent</CardTitle>
                            <CardDescription>
                                Guided industry wizard. No graph theory required.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Button asChild variant="outline">
                                <Link href="/agent-wizard">Start wizard</Link>
                            </Button>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader>
                            <CardTitle>Usage and billing</CardTitle>
                            <CardDescription>
                                Minutes, calls, WhatsApp, and M-Pesa on your plan.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Button asChild variant="outline">
                                <Link href="/billing">View usage</Link>
                            </Button>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader>
                            <CardTitle>Developers</CardTitle>
                            <CardDescription>
                                API keys, webhooks, and OpenAPI-style docs when you need them.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="flex gap-2">
                            <Button asChild variant="outline">
                                <Link href="/api-keys">API keys</Link>
                            </Button>
                            <Button asChild variant="outline">
                                <Link href="/agent-eval">Quality</Link>
                            </Button>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
