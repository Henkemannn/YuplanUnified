# Yuplan Unified — Security Baseline

**Status:** Living engineering security baseline, reviewed 2026-11-07. This file records security controls and verified evidence; it does **not** grant pilot or production approval. The current release/gate authority remains [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md). Do not add a competing MVP tracker here.

**Current verified product/security code checkpoint before docs-only commits:** `7286fb64355eca26c2016bbaabadf756989fc41f` — Gate 03G.1, pushed 2026-11-07. **Not deployed or live-verified.** The sole next-gate authority is `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md`.

## Non-negotiable principles

- AuthN (identity), AuthZ (role, tenant, site, department), data isolation and deployment guardrails are independent layers. Deny by default on every server-side resource access; never treat hidden UI controls as authorization.
- Preserve the existing working Admin/Kitchen/Unit Portal login and role/site binding, mandatory password change, `auth_version` invalidation and refresh JTI rotation, unless a reproducible defect demands an explicitly reviewed change.
- Protect the accepted Builder and Department Portal visuals; security changes must not restyle either.
- No production/test secrets, reset tokens, session cookies or personally identifying record data in Git, diagnostics, ordinary logs or reports. Do not read exposed historical cookie contents as part of remediation.
- Unit/department dietary data may require heightened privacy controls when it can identify a person.

## Verified in source / focused tests (through 2026-11-07)

| Area | Evidence | Current status and remaining check |
| --- | --- | --- |
| AuthN, roles and site/department boundaries | Existing login and role/site code, focused auth regression suites | Implemented foundations; final negative tenant/site/RBAC and iPad/mobile acceptance outstanding |
| Demo/deployed guard / session cookie | Gate 03C.1 correction in `core/config.py`: Fly/deployed deny before `testing` allowance; focused tests | **Code-fixed, not deployed proof.** Real deployed `Set-Cookie`, session flags and no-demo check still required at fresh staging release |
| Persistent failed-login throttling | `core/auth_rate_limit.py`, database-backed account/IP store and reservation semantics; migrations 0048 and 0049 | Implemented in source with isolated tests; hosted restart/concurrency/abuse verification still needed |
| Password reset | `core/password_reset.py`, `core/auth.py`, `0050_add_password_reset_storage.py`; hashed single-use expiring tokens, throttled request persistence, neutral anti-enumeration response and revocation flow | **Code and tests implemented.** No end-to-end live reset or production delivery proof yet |
| SMTP adapter | `core/password_reset_mailer.py`: TLS-required authenticated SMTP, text+HTML message, validated addresses and HTTPS reset URL | Tested with fake SMTP; actual Postmark delivery **pending** local manual smoke |
| SMTP/public base URL configuration | Gate 03G.1, commit `7286fb64`: env -> `Config.from_env()` -> Flask `PASSWORD_RESET_PUBLIC_BASE_URL`; explicit testing override preserved | **79/79 auth tests passed**, focused Ruff and diff check green. Current runtime env integration not hosted-verified |
| Central new-password policy | Gate 03F, `core/password_policy.py`, 15–1024 characters, Unicode and spaces accepted, small built-in denylist and optional deployment extension | Implemented across account flows; existing password verification remains supported; not a breach-corpus screening guarantee |
| Forced first-login and revocation | Existing `must_change_password`, `auth_version` and refresh JTI rotation contracts | Preserve through final reset/login E2E |
| HTML login UX / CSRF | Existing template/endpoint contracts, tests | Not yet signed off as complete live user experience; preserve rotating globe, review appropriate HTML feedback and CSRF |
| Legacy session artifact | `cookie.txt` previously removed from Git index and added to ignore | **Incident still open** if session material appears in Git history; index removal does not revoke credentials or purge history |

### Transactional email provider: Postmark

- The user created and secured the Postmark account and saved a **dedicated transactional SMTP Access Key / Secret Key** outside Git. Credentials are never to be sent to Copilot, ChatGPT, CI logs, docs, test fixtures or commits.
- `yuplan.se`: Postmark DKIM and Return-Path verified; one.com standard SPF activated; DMARC TXT created as `v=DMARC1; p=none`. User-provided Postmark screenshot shows approval/live account. This verifies configuration state **not actual deliverability**. DMARC aggregate reports are not set up; `p=none` requests monitoring rather than rejection.
- SMTP adapter settings for a later configured runtime (values are **not** secret material): `PASSWORD_RESET_SMTP_HOST=smtp.postmarkapp.com`, `PASSWORD_RESET_SMTP_PORT=587`, `PASSWORD_RESET_SMTP_SECURITY=starttls`, `PASSWORD_RESET_SMTP_FROM=no-reply@yuplan.se` (proposed). **Username = dedicated Postmark SMTP Access Key, password = dedicated SMTP Secret Key**; unlike Postmark's server API token variant, do not use the same token for both when separate SMTP keys are used.
- Other required environment variables: `PASSWORD_RESET_PUBLIC_BASE_URL` (actual public **HTTPS** URL of app, never marketing website), `PASSWORD_RESET_HMAC_SECRET` (separate strong secret), `AUTH_RATE_LIMIT_HMAC_SECRET` (separate), `PASSWORD_RESET_SMTP_USERNAME`, `PASSWORD_RESET_SMTP_PASSWORD`; optional timeout 10 seconds. Do not print their values.
- Gate 03G.1 **CLOSED**: after postmark mailer integration, env-based public reset URL was fixed, code/test commit `7286fb64` pushed. Gate 03G.2 **ORDER SENT / AWAITING REPORT**: prepare safe interactive manual SMTP smoke and isolated reset E2E; no actual delivery or completion claimed.
- Manual smoke should require the owner's explicit command, a controlled recipient and confirmation before SMTP send. Isolated local reset E2E may mock outgoing messages; do not claim that fake SMTP passes prove real deliverability. Keep any test tokens out of reports/logs.

### Environment boundary / deployment hold

- **No new Fly deployment or changes to its secrets, volumes or DB are authorized during current Kommun 1.1 implementation.** This is a product-owner decision to avoid premature double work.
- The old Fly app `yuplan-unified-staging` was inspected read-only on 2026-11-07. Machine `68320edf664468`, volume `yuplan_data`, SQLite at `/data/yuplan_pilot.db`, startup mutations disabled. **DB migration current 0020, deployed migration head 0023**, while active development migration head is **0050**. The existing Fly installation is historical (not used for active Yuplan development for about 9–10 months), **not a candidate to upgrade blindly**.
- No backup, migration, deployment, secrets update or restart was performed. No staging or restore acceptance is claimed. Historical `docs/staging_postgres_runbook.md` references a **different, older Fly app** and must not be treated as the inspected SQLite app's actual runbook.
- After Kommun 1.1 is accepted locally, design a **fresh current-code staging environment**, rehearse DB schema and backup/restore on isolated data, set credentials as runtime secrets, verify real public HTTPS reset, throttling, cookies, account recovery and session revocation, then obtain product-owner pilot sign-off. This is later release work, not the current Copilot gate.

## Before Kommun pilot GO — outstanding security acceptance

1. Finish local Gate 03G.2 and explicitly record mock-reset E2E and one authorized real SMTP test (if actually performed); preserve client and UI behavior.
2. Reconcile historical session/cookie exposure, determine whether credential/session revocation is required, and ensure historical data is not inadvertently copied into a fresh pilot deployment.
3. Validate secure auth cookies, deployed auth/dev guards, API vs HTML login feedback, CSRF and rate-limit resilience on the **new release candidate**, not the historical Fly app.
4. Test cross-tenant/site/department denial, recovery token one-time/expiry, password reset impact on existing sessions/JWTs, and rollback/restore.
5. Complete live Kommun manual walkthrough, appropriate regressions and explicit release/freeze acceptance; green unit tests alone never imply pilot GO.

## Phased security maturity (not current pilot implementation)

- **Kommun pilot:** scoped auth/RBAC, secure cookies, distributed throttling, safe reset, backup/restore, deployment and tenancy checks.
- **Yuplan 1.0:** admin MFA, security events/alerts, secret scanning, vulnerability scanning, periodic independent review.
- **Larger enterprise customers:** SSO (e.g. OIDC), phishing-resistant passkeys, documented onboarding/offboarding and advanced access audit.

Threat-model and requirements reference: OWASP ASVS and relevant NIST identity guidance. These are target standards, not a claim of certification.
