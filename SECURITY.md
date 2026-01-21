# Security Policy

This document describes how we handle vulnerabilities, security controls in code & CI, and expectations for responsible disclosure.

## Supported Versions
Only the latest released (tagged) minor version and the current `master` (development) branch receive security fixes. After GA (`v1.x`), previous minors may receive critical patches at our discretion.

| Version | Status | Security Fixes |
|---------|--------|----------------|
| `v1.0.0-beta` | Beta (baseline frozen) | Yes (critical + high) |
| `master` | Active development | Yes (all severities) |

## Reporting a Vulnerability
Email: `security@exempel.tld` (preferred)  
Alternative: Create a private GitHub Security Advisory ("Report a vulnerability" in the repo Security tab).

Please include (when possible):
* Affected endpoint / component
* Steps to reproduce (curl or minimal script)
* Observed vs. expected result
* Potential impact assessment
* Any CVSS vector you propose

Do NOT create a public issue for unpatched vulnerabilities.

### Response Targets
| Phase | Target SLA |
|-------|------------|
| Triage | 2 business days |
| First response / clarification | 5 business days |
| Fix for Critical | 7 days (best effort) |
| Fix for High | 14 days |
| Fix for Medium | 30 days |
| Fix for Low | 60 days |

We use a CVSS v3.1 inspired severity mapping. If exploitability is low and there is no data exposure, we may extend timelines.

### Disclosure Timeline
1. Reporter submits privately.
2. We acknowledge (≤ 5 business days).
3. Patch developed & reviewed under a private branch / fork.
4. Release fix + coordinated disclosure (CHANGELOG + optional security advisory). Credit given if desired.
5. If active exploitation is observed, we may accelerate release and publish limited interim guidance.

## Security Controls (CI & Runtime)
| Control | Description |
|---------|-------------|
| OpenAPI Baseline Enforcement | Prevents accidental breaking contract changes / unvetted surface expansion. |
| Semantic Diff (scripts/openapi_diff.py) | Detects narrowing & structural changes (type, format, required fields). |
| Rate Limiting (fixed + token bucket) | Mitigates brute force & abusive scraping patterns. |
| Audit Logging | Admin & limit changes persisted with retention cleanup script. |
| Feature Flags | Allows gradual, principal-of-least-change rollout. |
| Pre-commit Hooks | Lint + type guard before code lands. |
| pip-audit Workflow | Identifies vulnerable dependencies. |
| Release Readiness Script | Ensures baseline, tests, lint, diff status before tagging. |
| Error Hygiene | All 4xx/5xx errors use RFC7807 Problem Details. 429 always sets `Retry-After` header and includes `retry_after` (and `limit` when applicable). See ADR-001 and ADR-003. |


## Site Isolation Policy

- Non-superusers must be site-bound on login; missing binding returns 403 (`site_binding_required`) in JSON and 403 HTML for form login.
- `/ui/select-site` is superuser-only; non-superusers cannot switch sites via the selector.
- Alt2 flags and weekview mutations are strictly scoped by `site_id`; writes for another site are rejected.
- Single-site tenants auto-bind on login when possible; multi-site tenants without binding are denied (no fallback selector).

## Governance
All future security and protocol decisions must be captured as an ADR and referenced by ID in relevant docs and PRs (e.g., "See ADR-001"). See the ADR index at `adr/README.md`. For CSRF posture and rollout specifics, see ADR-002.

# Technical Security Controls

## JWT Authentication
Access & refresh tokens are HMAC signed (HS256) with support for secret rotation via `JWT_SECRETS`. Enforced claims and rejection reasons:

| Claim / Check | Behavior | Rejection Reason |
|---------------|----------|------------------|
| alg | Only HS256 (RS256 placeholder accepted for future) | `alg` |
| kid | Required for RS256 flow / rotation hint | `kid` |
| iss | Must match `JWT_ISSUER` (default `yuplan`) | `iss` |
| aud | Must include `JWT_AUDIENCE` | `aud` |
| exp | Expired beyond leeway -> reject | `exp` (message `token expired`) |
| nbf | Future beyond leeway -> reject | `nbf` (message `token not yet valid`) |
| iat (future) | If > now + leeway -> reject | `iat_future` |
| max age | If access iat older than `JWT_MAX_AGE_SECONDS` | `max_age` |
| revocation (refresh) | Stale JTI | `revoked` |

Other rejection reasons: `malformed`, `bad_header`, `bad_signature`, `bad_payload`, `type`, and each missing claim name.

Metric: `security.jwt_rejected_total{reason=*}` increments for every decode failure.

## CSRF Protection
See ADR-002 (Strict CSRF Rollout) for the governance decision and migration plan.
Production (TESTING=False) uses a double-submit token (`csrf_token` cookie + `X-CSRF-Token` header) OR strict same-origin check for mutating methods. Safe methods (GET/HEAD/OPTIONS) are always allowed. Exempt prefixes: `/auth/`, `/metrics`.

In test mode we currently bypass enforcement unless `STRICT_CSRF_IN_TESTS=1`, allowing incremental hardening. CSRF denials return RFC7807 problem+json with `detail` in {`csrf_missing`,`csrf_mismatch`,`origin_mismatch`}.

Metric: `security.csrf_blocked_total{reason=missing|mismatch|origin}`.

### Strict CSRF (Flag-Gated Migration)
An additional stricter layer can be enabled via env flag `YUPLAN_STRICT_CSRF=1` which activates a new middleware (`core/csrf.py`) *in addition to* legacy protections. Characteristics:
* Enforced only for selected prefixes initially: `/diet/`, `/superuser/impersonate/` (mutating methods).
* Per-session token stored in server session (rotated every 24h) and injected into templates as meta `<meta name="csrf-token" ...>` and helper `csrf_token_input()` for forms.
* Accepted via header `X-CSRF-Token` (preferred) or form field `csrf_token`.
* Failures return RFC7807 with types:
  * `https://example.com/problems/csrf_missing` (detail `csrf_missing`)
  * `https://example.com/problems/csrf_invalid` (detail `csrf_invalid`)
* JavaScript helper (`/static/js/http.js`) automatically attaches the token to mutating `fetch()` requests.
* Designed for incremental expansion of `ENFORCED_PREFIXES` after test coverage migration.

## Cookie Policy
| Cookie | Secure (prod) | HttpOnly | SameSite | Notes |
|--------|---------------|----------|----------|-------|
| Session | Yes | Yes | Lax | Framework-managed (Flask config) |
| csrf_token | Yes (prod) | No | Strict | Readable for double-submit, not an auth secret |

In DEBUG/TESTING we relax the Secure flag for local HTTP convenience.

## 405 Mapping
`MethodNotAllowed (405)` mapped to 404 envelope for compatibility. Metric: `http.405_mapped_to_404_total{method=*}`; warning log emitted with path & method.

## Rate Limiting & 429
Brute-force login and certain admin/feature endpoints enforce per-user / per-tenant limits. 429 responses include `Retry-After` header and JSON body with `retry_after` seconds. Tests ensure header is numeric and > 0.

## Security Headers (automatic)
`Strict-Transport-Security`, `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`. Set idempotently.

## Observability Summary
| Metric | Labels | Description |
|--------|--------|-------------|
| security.jwt_rejected_total | reason | JWT decode failures by reason |
| security.csrf_blocked_total | reason | CSRF denials |
| http.405_mapped_to_404_total | method | 405 responses mapped to 404 |
| audit.impersonation_start/stop/auto_expire (OTEL span) | action | Impersonation lifecycle (spans only if OTEL present) |

### Superuser Impersonation
Purpose: enforce principle-of-least-privilege. A `superuser` MUST impersonate a tenant admin context before performing write operations that mutate tenant-scoped data. Reads may still be direct depending on future policy.

Lifecycle:
1. POST `/superuser/impersonate/start` with `{tenant_id, reason}`
2. Request session stores: `tenant_id`, `reason`, `started_at`, `expires_at` (`IMPERSONATION_MAX_AGE_SECONDS`, default 900s), `admin_user_id`, snapshot of original roles.
3. Each request applies impersonation (before_request) promoting effective roles to include `admin` and overriding `g.tenant_id`.
4. Expiry: if `expires_at` passed the state auto-expires (cleared) and an audit event `impersonation_auto_expire` is recorded.
5. Manual stop: POST `/superuser/impersonate/stop` → audit event `impersonation_stop`.

Audit Events (in-memory buffer; future persistence):
- `impersonation_start` (actor_user_id, tenant_id, reason, expires_at)
- `impersonation_stop` (actor_user_id, tenant_id)
- `impersonation_auto_expire` (actor_user_id, tenant_id, started_at)

Problem Types (RFC7807):
- `https://example.com/problems/impersonation-required` with `detail: impersonation_required` when a superuser attempts a protected write without active impersonation.
- Generic forbidden retains `https://example.com/problems/forbidden` for legacy CSRF issues.
- Future: `https://example.com/problems/impersonation-expired` if we surface explicit expired state feedback instead of silent clearing.

UI: Active impersonation banner (orange) shows tenant, remaining seconds, reason, and Stop button; disappears automatically on expiry or stop.

Configuration:
- `IMPERSONATION_MAX_AGE_SECONDS` (env; default 900) – hard upper bound for a session; requires re-affirmation after expiry.

Security Rationale: forces deliberate escalation with auditable reason, constrains blast radius (time + scope), and provides operator visibility in support tooling.

All metrics are best-effort; if OpenTelemetry is absent they silently no-op.

## Future Work
- Full RS256 issuance & JWKS endpoint
- Strict CSRF enabled by default in tests once legacy fixtures refactored
- Additional audit logging export (structured) for JWT & CSRF denials

## Dependencies (pip-audit)
Before each release:
1. Run `pip-audit --strict` locally (or `make ready` if integrated later).
2. Fix or pin any Critical/High issues; document accepted Medium/Low in `SECURITY-NOTES.md` (future) if deferring.
3. CI soft gate example:
```yaml
- name: pip-audit
  run: |
    pip install pip-audit
    pip-audit || true  # TODO: remove '|| true' to hard fail later
```

## GitHub Actions Permissions
Principle: Default to `read-all` and explicitly widen per job only as needed.

Global restriction example:
```yaml
permissions: read-all
jobs:
  openapi-status:
    permissions:
      contents: write
      pull-requests: write
```
Remove `issues: write` unless actually posting issues. For PR comments use `pull-requests: write`.

## Secrets Handling
| Practice | Notes |
|----------|-------|
| Minimal secrets | Prefer short-lived tokens or environment-provided creds. |
| No secrets in repo | Validate via secret scanning (GitHub Advanced Security / trufflehog). |
| Rotation cadence | Quarterly for static tokens / credentials (✅ checklist). |
| Principle of Least Privilege | Scope tokens to required repo or environment only. |

Never log secrets (passwords/tokens). Seed scripts must mask secrets.

## Rate Limiting & Abuse Mitigation
* Fixed window and token bucket strategies supported per limit registry.
* 429 responses include `Retry-After` for polite backoff.
* Metrics: `rate_limit.hit` (`allow|block`) and `rate_limit.lookup` sources to monitor systemic pressure.
* Adjust per-tenant limits under feature flags for burst containment.

## RFC7807 Scope
Problem Details (RFC7807) is now canonical across all endpoints (401/403/404/409/422/429/500). `WWW-Authenticate` is included for 401 when appropriate. See ADR-003 for the adoption decision.

## Data Handling (PII / Telemetry)
| Aspect | Approach |
|--------|----------|
| PII in logs | Avoid user supplied free‑form fields; redact tokens / secrets. |
| Request IDs | `request_id` correlates across logs & problems `instance`. |
| Multi-tenancy | Tenant ID tag in logs & metrics (partitioning & forensic filtering). |
| Metrics | Aggregate numeric / categorical (no raw content bodies). |
| Retention | Audit events truncated via retention cleanup script (configurable). |

## Responsible Disclosure Checklist (Maintainers)
| ✅ | Task |
|----|------|
| ✅ | Triage new report within 2 business days |
| ✅ | Classify severity (CVSS rough score) |
| ✅ | Create private fix branch (no public issue) |
| ✅ | Run `pip-audit` before release cut |
| ✅ | Review workflow permissions (least privilege) each release |
| ✅ | Rotate tokens quarterly |
| ✅ | Verify rate limit protections (simulate abusive pattern) |
| ✅ | Confirm audit retention job run |

## Maintainer Release Security Checklist
| ✅ | Step |
|----|------|
| ✅ | `make ready` green (tests, diff, lint) |
| ✅ | `pip-audit` shows no unmitigated Critical/High |
| ✅ | Secrets scan (periodic) shows no leaks |
| ✅ | Baseline `specs/openapi.baseline.json` matches current spec |
| ✅ | Review new dependencies for license & security posture |
| ✅ | Rate limit changes documented in CHANGELOG |
| ✅ | Deprecation headers (if any) validated |

## CVSS Inspired Severity Mapping (Guidance)
| Severity | Typical Impact |
|----------|----------------|
| Critical | RCE, auth bypass, sensitive data exfiltration |
| High | Privilege escalation, significant data tampering |
| Medium | Limited data exposure, authorization edge cases |
| Low | Information disclosure (non-sensitive), minor spoofing |
| Informational | Hardening opportunity / best practice deviation |

## Contact & Attribution
If you wish to be credited, include the preferred name or handle. We will not publish reporter details without consent.

Thank you for helping keep the platform secure.
