/** Hand-written SDK client for the Dograh public API platform. */

import { ApiError } from "./errors.js";

export interface PlatformClientOptions {
    baseUrl?: string;
    apiKey?: string;
    timeoutMs?: number;
    fetch?: typeof fetch;
}

export class PlatformClient {
    private readonly baseUrl: string;
    private readonly apiKey?: string;
    private readonly timeoutMs: number;
    private readonly fetchImpl: typeof fetch;

    constructor(options: PlatformClientOptions = {}) {
        this.baseUrl = `${(options.baseUrl ?? "http://localhost:8000").replace(/\/$/, "")}/api/v1/platform`;
        this.apiKey = options.apiKey;
        this.timeoutMs = options.timeoutMs ?? 30_000;
        this.fetchImpl = options.fetch ?? fetch;
    }

    async info(): Promise<Record<string, unknown>> {
        return this.request("GET", "");
    }

    async routes(): Promise<Array<Record<string, unknown>>> {
        return this.request("GET", "/routes");
    }

    async usage(scope: "organization" | "api_key" = "organization"): Promise<Record<string, unknown>> {
        return this.request("GET", `/usage?scope=${scope}`);
    }

    async listWebhooks(): Promise<Array<Record<string, unknown>>> {
        return this.request("GET", "/webhooks");
    }

    async createWebhook(input: {
        name: string;
        url: string;
        events: string[];
    }): Promise<Record<string, unknown>> {
        return this.request("POST", "/webhooks", { body: JSON.stringify(input) });
    }

    async testWebhook(subscriptionUuid: string): Promise<Record<string, unknown>> {
        return this.request("POST", `/webhooks/${subscriptionUuid}/test`);
    }

    async triggerCall(
        triggerPath: string,
        input: {
            phone_number: string;
            initial_context?: Record<string, unknown>;
            telephony_configuration_id?: number;
        },
    ): Promise<Record<string, unknown>> {
        return this.request("POST", `/calls/trigger/${triggerPath}`, {
            body: JSON.stringify(input),
        });
    }

    async triggerCallByWorkflow(
        workflowUuid: string,
        input: {
            phone_number: string;
            initial_context?: Record<string, unknown>;
            telephony_configuration_id?: number;
        },
    ): Promise<Record<string, unknown>> {
        return this.request("POST", `/calls/workflow/${workflowUuid}`, {
            body: JSON.stringify(input),
        });
    }

    private async request(
        method: string,
        path: string,
        init: { body?: string } = {},
    ): Promise<any> {
        const headers: Record<string, string> = {
            Accept: "application/json",
        };
        if (this.apiKey) {
            headers["X-API-Key"] = this.apiKey;
        }
        if (init.body) {
            headers["Content-Type"] = "application/json";
        }

        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeoutMs);
        try {
            const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
                method,
                headers,
                body: init.body,
                signal: controller.signal,
            });
            const text = await response.text();
            if (!response.ok) {
                let message = text;
                try {
                    const parsed = JSON.parse(text) as { detail?: string };
                    message = parsed.detail ?? text;
                } catch {
                    // keep raw text
                }
                throw new ApiError(response.status, message, text);
            }
            return text ? JSON.parse(text) : null;
        } finally {
            clearTimeout(timer);
        }
    }
}
