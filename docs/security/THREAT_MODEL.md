# ZuriFlow / Dograh threat model and security controls

This document describes **engineering controls that exist in the product today**.
It is **not** a certification, audit report, or claim of compliance with the Kenya
Data Protection Act, ODPC guidance, PCI DSS, ISO 27001, SOC 2, HIPAA, or any
other legal framework. Legal and compliance review is still required before
making any regulatory claims.

## Scope

ZuriFlow is a multi-tenant voice AI platform (FastAPI, Next.js, PostgreSQL,
Redis, MinIO). Tenant isolation is based on `organization_id`.

## Threats and implemented controls

| Threat | Implemented control | Residual risk / review needed |
| --- | --- | --- |
| Stolen passwords | bcrypt hashes, password complexity, login rate limit, lockout | Password storage KMS/HSM, phishing-resistant MFA for all tenants |
| Session theft | Short-lived access JWT, refresh rotation with reuse detection | Cookie `Secure`/`HttpOnly` on all deployments; Stack Auth path is separate |
| Missing MFA | Optional TOTP + recovery codes for local auth | Not enforced; Stack Auth MFA is provider-side |
| Privilege abuse | Expanded RBAC (Owner, Admin, Operations Manager, Agent Manager, Finance, Support Agent, Analyst, Developer, Read Only) | Many routes still authenticate with `get_user` only; permission checks are incomplete |
| Cross-tenant reads | Org-scoped DB lookups for workflows, campaigns, recordings, API keys, documents; 404 on mismatch | Unscoped helpers remain for telephony/system jobs (`get_workflow_by_id`, `get_document_by_id`) |
| Prompt injection | Untrusted workflow instructions quarantined in Kenyan system prompts | Not applied to every prompt path; models can still be socially engineered |
| Tool abuse | Runtime category allowlist; HTTP URL scheme + SaaS SSRF checks; LLM cannot supply the URL | OSS mode still allows private URLs by design; MCP catalog needs ongoing review |
| Webhook spoofing | Provider signature verification where configured (telephony, WhatsApp, M-Pesa when secret set) | M-Pesa HMAC is optional if no secret; org-in-path must stay bound to signed identity |
| API abuse | API keys hashed; create/list keys require `api_key` permissions | No global API quota in this change; public run tokens remain capability URLs |
| Payment abuse | Finance/billing permissions for payment analytics | STK push and callback integrity still depend on Daraja secrets and ops process |
| Recording/transcript leakage | Recording routes require `recording:read`; signed URLs org-prefixed | Public/share tokens and MinIO bucket policy in OSS can still leak if misconfigured |
| Credential exposure | Secrets in org credential store; JWT secret production check | Default `OSS_JWT_SECRET` is insecure until changed; do not commit `.env` |
| WebSocket auth | Signaling uses `get_user_ws` | `agent_stream` identifies by workflow UUID without a user session |
| Redis / MinIO / DB | Network isolation is an operations concern; app uses env URLs | Redis AUTH, MinIO private buckets, Postgres roles, and TLS are **deployment** controls, not claimed here |

## Sensitive data classification

| Data | Class | Least-privilege permission |
| --- | --- | --- |
| Phone numbers | Restricted | `conversation_pii:read` |
| Recordings | Restricted | `recording:read` |
| Transcripts | Restricted | `transcript:read` |
| Payment information | Restricted | `payment_analytics:read` |
| API credentials | Restricted | `api_key:read` / `api_key:write` |
| Customer CRM fields | Confidential | `conversation_pii:read` |
| Aggregated analytics | Internal | `analytics:read` |

## Audit

Security-sensitive actions append rows to `security_audit_events` (insert-only in
application code). Organization admin actions continue to use
`organization_audit_logs`. Database superusers can still modify rows; true
immutability needs WORM storage or append-only DB roles — **not implemented**.

## Automated tests

- `api/tests/test_security_hardening.py` — password policy, TOTP, JWT types, lockout, RBAC, prompt quarantine, tool policy, org-scope source checks
- Existing `api/tests/test_tenant.py` and `api/tests/test_tenant_route_isolation.py`

## Explicitly not claimed

- Regulatory compliance or certification
- Perfect prompt-injection immunity
- Physical, network, or cloud-account hardening
- End-to-end encryption of recordings at rest beyond object-store configuration
- Independent penetration test (recommended before production)

## Production checklist (operations)

1. Set a unique `OSS_JWT_SECRET` (≥32 characters).
2. Disable anonymous MinIO access; use private buckets and short-lived signed URLs.
3. Require Redis AUTH and TLS between app, Redis, Postgres, and object storage.
4. Put login, webhooks, and public APIs behind WAF/rate limits at the edge.
5. Enable MFA for operators; review RBAC assignments quarterly.
6. Commission a legal review for Kenya DPA / ODPC and a payment review if processing M-Pesa at scale.
