# Yuplan Unified — Security Baseline

**Status:** Living engineering security baseline, reviewed 2026-11-07. This file records security controls and verified evidence; it does **not** grant pilot or production approval. The current release/gate authority remains [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md). Do not add a competing MVP tracker here.

**Current verified product/security code checkpoint before docs-only commits:** `a8fed697826623513243036faa3efeab7a061b06` — Gate 03H.2B HTML login UX, pushed 2026-11-07 (prior reset expiry checkpoint `c53b945288fb832b4b388a39ee076e2f1dc600e4`). **Not deployed or hosted-live-verified.** The sole next-gate authority is `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md`.

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
| Password reset | `core/password_reset.py`, `core/auth.py`, `0050_add_password_reset_storage.py`; hashed single-use expiring tokens, throttled request persistence, neutral anti-enumeration response and revocation flow | **Code/tests and isolated-browser reset lifecycle verified.** Standalone real provider SMTP delivery was inbox-confirmed; full hosted real reset not yet verified |
| SMTP adapter | `core/password_reset_mailer.py`: TLS-required authenticated SMTP, text+HTML message, validated addresses and HTTPS reset URL | Fake-SMTP adapter tests green; **real external Postmark SMTP smoke succeeded and inbox delivery owner-confirmed** 2026-11-07. Hosted reset endpoint **not** live-tested |
| SMTP/public base URL configuration | Gate 03G.1, commit `7286fb64`: env -> `Config.from_env()` -> Flask `PASSWORD_RESET_PUBLIC_BASE_URL`; explicit testing override preserved | **79/79 auth tests passed**, focused Ruff and diff check green. Current runtime env integration not hosted-verified |
| Central new-password policy | Gate 03F, `core/password_policy.py`, 15–1024 characters, Unicode and spaces accepted, small built-in denylist and optional deployment extension | Implemented across account flows; existing password verification remains supported; not a breach-corpus screening guarantee |
| Forced first-login and revocation | Existing `must_change_password`, `auth_version` and refresh JTI rotation contracts | Preserve through final reset/login E2E |
| HTML login UX / CSRF | Gate 03H.2B, `core/auth.py`, browser acceptance and auth regression suite | **Code and isolated browser PASS:** generic Swedish HTML 401/429 messages, correct Retry-After, unchanged JSON/API behavior and globe, 390px viewport; **82 auth tests passed**. Owner in-person and hosted acceptance outstanding |
| Legacy session artifact | `cookie.txt` previously removed from Git index and added to ignore | **Incident still open** if session material appears in Git history; index removal does not revoke credentials or purge history |

### Transactional email provider: Postmark

- The user created and secured the Postmark account and saved a **dedicated transactional SMTP Access Key / Secret Key** outside Git. Credentials are never to be sent to Copilot, ChatGPT, CI logs, docs, test fixtures or commits.
- `yuplan.se`: Postmark DKIM and Return-Path verified; one.com standard SPF activated; DMARC TXT created as `v=DMARC1; p=none`. User-provided Postmark screenshot shows approval/live account. Provider configuration and **owner-confirmed SMTP inbox delivery** verified; this does not constitute hosted Yuplan password-reset mailer integration acceptance. DMARC aggregate reports are not set up; `p=none` requests monitoring rather than rejection.
- SMTP adapter settings for a later configured runtime (values are **not** secret material): `PASSWORD_RESET_SMTP_HOST=smtp.postmarkapp.com`, `PASSWORD_RESET_SMTP_PORT=587`, `PASSWORD_RESET_SMTP_SECURITY=starttls`, `PASSWORD_RESET_SMTP_FROM=no-reply@yuplan.se` (proposed). **Username = dedicated Postmark SMTP Access Key, password = dedicated SMTP Secret Key**; unlike Postmark's server API token variant, do not use the same token for both when separate SMTP keys are used.
- Other required environment variables: `PASSWORD_RESET_PUBLIC_BASE_URL` (actual public **HTTPS** URL of app, never marketing website), `PASSWORD_RESET_HMAC_SECRET` (separate strong secret), `AUTH_RATE_LIMIT_HMAC_SECRET` (separate), `PASSWORD_RESET_SMTP_USERNAME`, `PASSWORD_RESET_SMTP_PASSWORD`; optional timeout 10 seconds. Do not print their values.
- Gate 03G.1 **CLOSED**: env-based public reset URL fixed, code/test commit `7286fb64` pushed. Gate 03G.2 **POSTMARK DEVELOPMENT CLOSED / HOSTED ACCEPTANCE PENDING**: the adapter was not changed; Copilot added one explicit expiry-at-30-min regression in `tests/auth/test_password_reset.py`; **66 focused tests passed**, Ruff and diff check green. Owner ran controlled Python `smtplib` STARTTLS auth/send against Postmark port 587 with dedicated Access Key and Secret Key; Postmark accepted the email and the owner **confirmed receipt** at `info@yuplan.se`. No real Yuplan-app reset was exercised. **The expiry test was committed/pushed as `c53b945288fb832b4b388a39ee076e2f1dc600e4`.**
- Gate 03H.1 local-browser scenarios passed except a genuine HTML error-display UX defect (raw JSON). Gates 03H.2/03H.2B corrected HTML 401 and 429 to reuse the original Swedish Yuplan login template, preserved JSON/API, throttle and CSRF, and verified actual browser 401 → 401 → 429, Retry-After, post-lockout success and 390px mobile viewport. **82/82 auth tests and Ruff passed; code committed/pushed at `a8fed697826623513243036faa3efeab7a061b06`.** Owner manual UX review and hosted integration remain pending.
- The manually authorized standalone SMTP delivery smoke has passed. This proves real Postmark SMTP auth, submission and receipt, **not** hosted `POST /auth/forgot` recovery. An initial .NET `SmtpClient` attempt failed with `4.7.1 Relay access denied`; Python `smtplib` succeeds, and the application uses `smtplib`, so do not change the app mailer due solely to the .NET failure. Keep any reset tokens out of reports/logs. A Server API Token was visible in an earlier user screenshot and should be **rotated/revoked by the owner** (confirm rotation before closure of provider account security).

### Environment boundary / deployment hold

- **No new Fly deployment or changes to its secrets, volumes or DB are authorized during current Kommun 1.1 implementation.** This is a product-owner decision to avoid premature double work.
- The old Fly app `yuplan-unified-staging` was inspected read-only on 2026-11-07. Machine `68320edf664468`, volume `yuplan_data`, SQLite at `/data/yuplan_pilot.db`, startup mutations disabled. **DB migration current 0020, deployed migration head 0023**, while active development migration head is **0050**. The existing Fly installation is historical (not used for active Yuplan development for about 9–10 months), **not a candidate to upgrade blindly**.
- No backup, migration, deployment, secrets update or restart was performed. No staging or restore acceptance is claimed. Historical `docs/staging_postgres_runbook.md` references a **different, older Fly app** and must not be treated as the inspected SQLite app's actual runbook.
- After Kommun 1.1 is accepted locally, design a **fresh current-code staging environment**, rehearse DB schema and backup/restore on isolated data, set credentials as runtime secrets, verify real public HTTPS reset, throttling, cookies, account recovery and session revocation, then obtain product-owner pilot sign-off. This is later release work, not the current Copilot gate.

## Before Kommun pilot GO — outstanding security acceptance

1. **Owner acceptance still pending** for login lockout/unlock, friendly HTML errors, password recovery and mobile/iPad UX in a safe test account. The code and focused isolated browser gates 03G.2 and 03H.2B are closed and both commits pushed. SMTP auth/send/inbox delivery confirmed separately; hosted real-app password recovery remains later release acceptance. Confirm rotation of previously exposed Postmark Server API Token.
2. Reconcile historical session/cookie exposure, determine whether credential/session revocation is required, and ensure historical data is not inadvertently copied into a fresh pilot deployment.
3. Validate secure auth cookies, deployed auth/dev guards, API vs HTML login feedback, CSRF and rate-limit resilience on the **new release candidate**, not the historical Fly app.
4. Test cross-tenant/site/department denial, recovery token one-time/expiry, password reset impact on existing sessions/JWTs, and rollback/restore.
5. Complete live Kommun manual walkthrough, appropriate regressions and explicit release/freeze acceptance; green unit tests alone never imply pilot GO.

## Phased security maturity (not current pilot implementation)

- **Kommun pilot:** scoped auth/RBAC, secure cookies, distributed throttling, safe reset, backup/restore, deployment and tenancy checks.
- **Yuplan 1.0:** admin MFA, security events/alerts, secret scanning, vulnerability scanning, periodic independent review.
- **Larger enterprise customers:** SSO (e.g. OIDC), phishing-resistant passkeys, documented onboarding/offboarding and advanced access audit.

Threat-model and requirements reference: OWASP ASVS and relevant NIST identity guidance. These are target standards, not a claim of certification.
