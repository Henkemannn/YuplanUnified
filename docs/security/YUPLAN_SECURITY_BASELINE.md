# Yuplan Unified — Security Baseline

**Status:** Living engineering security baseline, reviewed 2026-11-06. This file records security controls and verified evidence; it does **not** grant pilot or production approval. The current release/gate authority remains [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md). Do not add a competing MVP tracker here.

**Current security code checkpoint:** `dbfa1534c8ba0781b630cfc2279e0029b113dfd3` — Gate 03C, pushed 2026-11-06. **Not deployed or live-verified** based on available evidence.

## Non-negotiable principles

- AuthN (identity), AuthZ (role, tenant, site, department), data isolation and deployment guardrails are independent layers. Deny by default on every server-side resource access; never treat hidden UI controls as authorization.
- Preserve the existing working Admin/Kitchen/Unit Portal login and role/site binding, mandatory password change, `auth_version` invalidation and refresh JTI rotation, unless a reproducible defect demands an explicitly reviewed change.
- Protect the accepted Builder and Department Portal visuals; security changes must not restyle either.
- No production/test secrets, reset tokens, session cookies or personally identifying record data in Git, diagnostics, ordinary logs or reports. Do not read exposed historical cookie contents as part of remediation.
- Unit/department dietary data may require heightened privacy controls when it can identify a person.

## Verified in source / focused tests

| Area | Current evidence | Status / limitation |
| --- | --- | --- |
| Ordinary identity, role/site flows | Prior login suites and Gate 03C focused tests: 46 passed; focused Ruff passed | Implemented; real multi-tenant route and iPad acceptance pending |
| Sessions | `auth_version`, forced password change and refresh JTI rotation already exist | Preserve; recovery must revoke prior credentials |
| Session cookies | Gate 03C sets Flask session `Secure` for non-local/test mode, preserves `HttpOnly` and `SameSite=Lax`; test confirms Set-Cookie in simulated deployed mode | Actual Fly response headers **not verified** |
| Demo/dev entry points | Gate 03C central `auth_bypass_allowed()` reused for simple demo login, dev login, demo UI/route enumerator and test login; unknown environment intended fail-closed | **Follow-up C.1 required:** helper checks `testing` before `FLY_APP_NAME`, so Fly + TESTING=True remains an exception; do not claim unconditional Fly deny |
| Credential throttling | `core/auth.py` uses process-local in-memory failed-login store | **Open:** shared, atomic persistence / restart behavior |
| Self-service password recovery | `GET /auth/forgot` renders placeholder; no verified email/token workflow | **Open:** hashed single-use expiring token, anti-enumeration, abuse controls, session/JTI revocation |
| HTML login errors | Form POST may return JSON 401/429 instead of friendly login feedback | **Open:** preserve API response contract while improving form UX |
| CSRF / cookies / proxies | Login form has CSRF field; current /auth exemptions and proxy handling require review | **Open:** explicit security decision and deployment-level verification |
| Session file in Git | `cookie.txt` untracked from index and added to `.gitignore` in Gate 03C | **Open incident:** remains in historical commits; assume potentially compromised until validity/session revocation and repository history remediation are assessed |

## Gate 03C.1 — immediate correction

The current helper `core/config.py:auth_bypass_allowed(testing=...)` returns True for `testing=True` before checking `FLY_APP_NAME`. Required order: platform/deployed-context deny must take precedence over test/dev allowances. Add targeted regression for `FLY_APP_NAME` + `APP_ENV=dev` + `TESTING=True` and for session `Secure` in this case. Verify no regression in isolated local tests. Also inspect for equivalent high-risk dev entry points not covered by the shared helper. No deploy, broad refactor, or UI changes in this gate.

## Before Kommun pilot GO — explicit checks

1. Verify actual Fly app name, intended runtime mode, deployed SHA, demo/dev env presence as boolean only, and real session-cookie attributes. Do not dump secret values.
2. Revoke/expire any relevant captured session(s). Removing a tracked cookie file in a later commit does not clean history or revoke prior tokens; plan any signing-key rotation separately because of session impact.
3. Implement distributed login throttling, then self-service password recovery; use isolated tests for concurrency/restart and reset token single-use, expiry, enumeration resistance and old-session revocation.
4. Verify negative tenant/site/department RBAC access, HTTPS, CSRF, logs and safe headers, backup restore, incident handling, and final live login/portal UX on iPad/mobile.
5. Perform product-owner acceptance, full appropriate regression and deployment checks; only then consider Kommun 1.1 pilot GO.

## Phased security maturity (not current pilot implementation)

- **Kommun pilot:** scoped auth/RBAC, secure cookies, distributed throttling, safe reset, backup/restore, deployment and tenancy checks.
- **Yuplan 1.0:** admin MFA, security events/alerts, secret scanning, vulnerability scanning, periodic independent review.
- **Larger enterprise customers:** SSO (e.g. OIDC), phishing-resistant passkeys, documented onboarding/offboarding and advanced access audit.

Threat-model and requirements reference: OWASP ASVS and relevant NIST identity guidance. These are target standards, not a claim of certification.
