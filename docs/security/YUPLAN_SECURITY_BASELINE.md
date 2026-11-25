# Yuplan Unified — Security Baseline

## SEC-01 — 2026-11-25 HEALTH-11 full-suite GREEN checkpoint

**Current operational status:** See [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md), CURRENT 2026-11-25. Historical findings and previous HEALTH-10 failure analysis below remain for audit only; they do not represent the latest test status.

- **Verified product checkpoint:** `9ce2952cbeb12d2a8e7adf53c53135b2a1284a2d` on `feat/planera-app-shell-2026-03-03`. HEALTH-10R three-test-file commit pushed and GitHub verified; no production changes.
- **HEALTH-11 complete pytest:** **3,003 tests; 2,988 PASS / 0 FAIL / 0 ERROR / 15 SKIP**, exit 0, 24m53s, three existing deprecation warnings. Compared with HEALTH-10: all **10 FAIL→PASS**, **0** PASS regressions, **0** identities added/removed, skip set unchanged. Isolated pytest DB, original protected pilot DB SHA-256 unchanged `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`. Artifacts at local `%TEMP%\yuplan-health-11\` (JUnit + output). This evidence comes from Copilot's complete local run/report; source checkpoint independently verified on GitHub.
- **HEALTH-10R root cause/remedy:** shared session test database retained orphaned `kitchen_user_sites.user_id` values and test seeds reused IDs; new IDs now exceed maxima from both `users` and binding table without destructive cleanup. Admin Users site-binding test now checks active source (`users.site_id` or `kitchen_user_sites`) and dual-source consistency. Tested 20/20 core, 24/24 original predecessor order, 53/53 security/auth, and now complete HEALTH-11 GREEN. **Test recovery CLOSED.**
- **F08 scoped CLOSED and full-suite-green:** shared route-local `_authorize_report_scope` call on `/ui/admin/report/week` before site/department reads; focused report/export 26/26 PASS and full-suite report tests PASS. Previously upstream login rejected the exercised site/tenant manipulation; no exploit under current login was demonstrated. Avoid asserting that every conceivable report/export route was audited.
- **F09 PARTIAL:** two legacy week JSON/CSV GETs closed with verified site/tenant checks and 109/109 targeted PASS. Remaining ID-based Planera write APIs still require audit/repair. **NEXT: SEC-F09-REMAINING**, then **F10 OPEN P0** anonymous demo real-data access. F11 runtime/staging secrets proof OPEN; JWT RS256/HMAC and F12–F15 OPEN. F01–F07 and SEC-DELETE paths previously scoped CLOSED.
- **Process:** one scoped Copilot order/report/review/guarded commit; focused negative/positive tenant/site/security tests on each fix; full-suite checkpoints roughly every 2–3 significant security changes, not every small order. No pilot GO, new staging GO, migration or deployment solely from green tests.
- **Sync caution:** the docs-only commits above product HEAD require user-side clean, verified fast-forward before further local code work.

---

## SEC-01 — HEALTH-10 and F08 review overlay (2026-11-24)

**Primary operational authority:** [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md), CURRENT HEALTH-10. This overlay supersedes older next-action assertions; historical scoped evidence remains.

**Product HEAD independently verified before documentation-only update:** `3eaad9816bfbadfef0baeb95b82a8ba8ee180bda` on `feat/planera-app-shell-2026-03-03`, owner-verified push and Git CLEAN.

- **F08 (scoped code CLOSED, full regression OPEN):** `/ui/admin/report/week` received shared `_authorize_report_scope()` check before data reads; focused report + CSV/XLSX/PDF/API suite **26/26 PASS**, including a spy test proving the guard is invoked. Upstream authentication already denied attempted cross-site/tenant tampering; route lacked defense-in-depth, but no active-login data leakage was reproduced. Three F08 report tests fail under HEALTH-10 full-suite order due to binding uniqueness fixture collision; **do not claim whole F08 test matrix GREEN**.
- **F09:** JSON/CSV legacy week GET routes scoped CLOSED, 109/109 focused PASS; other original-F09 resource-ID routes not globally certified.
- **F01–F07 / SEC-DELETE-01/-02:** previously reviewed scoped CLOSED; avoid speculative reopen. **F10 OPEN P0**, **F11 code closed/runtime open**, **F12–F15 OPEN P1**, **JWT RS256/HMAC check OPEN**.
- **HEALTH-10 full pytest:** 3,003 cases = **2,978 PASS / 10 FAIL / 0 ERROR / 15 SKIP**, exit 1, **47m14s**. HEALTH-09: 2,959 PASS / 13 FAIL / 15 SKIP (2,987 cases). 6 old failures fixed, 7 old remain, 3 new F08 full-order failures; no deleted test identities. Nine failures `kitchen_user_sites.user_id` uniqueness across six login UI parameterizations and three F08 tests. Remaining failure: admin staff-create site-binding `NoneType` assertion. Treat fixture attribution as hypothesis until proven; preserve auth/site fail-closed. No F09 or SEC-DELETE full-suite failures.
- **Immediate next gate HEALTH-10R:** targeted analysis→fix→bounded combined-order regression for these 10, then reviewed code commit; only afterwards one full-suite rerun to prove test-order stability. Do not run the ~47-minute full suite at every small gate.
- **Protected original and backup SHA-256:** `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`, verified unchanged before and after HEALTH-10. No deployment, migration or pilot acceptance. Docs-only GitHub updates must be synced via verified CLEAN fast-forward before local edits.

---

## SEC-01 status overlay — 2026-11-24 (source and tests verified)

**Operational status authority:** [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md), CURRENT 2026-11-24. This overlay supersedes the Nov 22 status/next-gate statements below; historical security evidence remains unmodified.

**Latest verified product/security HEAD before docs-only updates:** `9c6d98c159d970de1db8dd252dc3f718c687da01` on `feat/planera-app-shell-2026-03-03`; owner confirmed push, remote match, CLEAN worktree. Protected pilot SQLite and separately verified backup each SHA-256 `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`. The Nov 22 `eca346d2…` product checkpoint and `acf627…` pilot hash are **historical**, not today's guard. No Fly deployment, original-DB migration or fresh staging acceptance.

### New reviewed/pushed security and recovery evidence

| Work / commit | Fix and focused evidence |
| --- | --- |
| **SEC-DELETE-01** `da53d6137957ee5e4d02ca1a3327b4e92ca3800d` | Atomic scoped special-diet deletion across duplicate UI registrations; blocks cross-tenant/null-site deletion. Scoped CLOSED. |
| **SEC-DELETE-02** `9f9af654ff632a0a35d1d3708f5119d21a485664` | Strict shared tenant/site resolver for real login, current sessions and Bearer/JWT; conflicts, missing/mismatched bindings, deactivation and auth-version invalidation denied. Scoped CLOSED. |
| **HEALTH-09D** `f54ef73d239923432e3afde3cd299d6bd1fc9c03` | Unifies `_user_has_current_site_binding` with strict resolver to support legacy `users.site_id` and kitchen bindings consistently; targeted original 13/13, historical 81/81, six modules 28/28, auth/real-actor 31/31 PASS. Full suite not repeated. |
| **SEC-F09-LEGACY** `9c6d98c159d970de1db8dd252dc3f718c687da01` | Real-account login reproduced HTTP 200 leakage from cross-site and cross-tenant Planera week JSON/CSV. `core/planera_api.py` now checks site tenant and authenticated ordinary-user site regardless of absent/false `site_lock`. 109/109 targeted tests PASS; two GET week endpoints scoped CLOSED. |

### Full pytest status

HEALTH-09 executed **2,987 cases = 2,959 passed + 13 failed + 15 skipped**, ~17m46s, at prior HEAD `9f9af654…`. The 13 failures have passed focused recovery (13/13), but **no new whole-suite run occurred on `f54ef73…` or `9c6d98…`**. Existing test fixtures and tests alone do not constitute independent security proof or pilot GO. Final complete pytest awaits remaining SEC-01 changes.

### Finding ledger (no blanket closures)

| Finding | State / next action |
| --- | --- |
| **F01–F07** | Previously **scoped CLOSED**, same audited surfaces and limitations as Nov 22; do not reopen absent regression. |
| **F08** | **OPEN (next: SEC-F08-CLOSE)**. Reconcile actual HTML/CSV/XLSX/PDF/API report/export routes with current security tests, real-user login, bound site, cross-tenant/site/department and 304/ETag denial. Prior tests such as `tests/ui/test_report_site_isolation_security.py` exist, but are not F08 final signoff. |
| **F09** | **PARTIAL**: `/api/planera/week` and `/api/planera/week/csv` scoped CLOSED, including tampered `site_id` with `site_lock=True/False/missing`. Confirm any remaining original F09 ID-based write routes separately, without repeating protected work. |
| **F10** | **OPEN P0**: anonymous demo real-data access. |
| **F11** | **Code/scoped CLOSED**, runtime/fresh-staging secrets and negative validation OPEN. |
| **F12–F15** | **OPEN P1**: support authorization, upload bounds, temporary-password UI, Weekview runtime-schema mutations. |
| **JWT RS256/HMAC** | **OPEN**: algorithm-confusion and secrets negative-path verification. |

**Working rules:** Tenant = kund, Site = arbetsplats, ordinary user permanently bound to exactly one verified site (no picker, no `site_lock` bypass); superuser/support under separately explicit policy; fail-closed regardless of session/query tampering. Protected SQLite never used for pytest. No full pytest until remaining SEC scoped remediations are reviewed. One Copilot order → report → review → guarded commit. Docs-only GitHub commits must be fast-forwarded locally before development resumes. **No pilot, deployment, or migration approval.**

---
## SEC-01 current remediation overlay — 2026-11-22

**Latest verified source checkpoint:** feature branch feat/planera-app-shell-2026-03-03, product/security HEAD **eca346d2fa6368843d1486b3fb124cfd7297cb11** (owner-verified local/remote matched, worktree clean). This overlay supersedes dated 2026-11-07 next-step claims below. The **one operational task/status authority** is [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md).

**Astra SEC-01:** 15 findings (F01–F11 HIGH; F12–F15 MEDIUM), plus a separate JWT RS256/HMAC algorithm concern.

| Finding | Disposition from targeted code/test reports |
| --- | --- |
| F01 Admin/Notes/Audit authorization | Scoped CLOSED |
| F02 Menu API authorization | Scoped CLOSED |
| F03 Dish/Menu site/tenant relationships, Municipal, import, Builder and reference paths | CLOSED for audited paths; tested copy migration through 0054 |
| F04 Builder import auth/session | Scoped CLOSED |
| F05 denied-login stale session | Scoped CLOSED |
| F06 refresh-token accepted as Bearer | Scoped CLOSED |
| F07 revoked/deactivated user binding | Scoped CLOSED |
| F08 export data leakage | **OPEN — NEXT** |
| F09 Planera cross-site | **OPEN** |
| F10 anonymous real-data demo | **OPEN** |
| F11 strong SECRET_KEY | Code/scoped CLOSED; deployment configuration validation OPEN |
| F12 support scope | **OPEN** |
| F13 upload bounds | **OPEN** |
| F14 temporary password flash | **OPEN** |
| F15 Weekview runtime schema repair | **OPEN** |
| JWT RS256 confusion under HMAC JWT_SECRETS | **OPEN, separately track** |

**F03 evidence/limits:** focused Dish/Municipal 29 passed; Builder/import 17 passed; migrations 13 passed; selected combined suite 290 passed / 1 existing skip; prior Admin+Core suite 302 passed / 1 existing skip. Pilot database was migrated **only as an isolated copy** from 0050 to 0054, preserving 2 tenants, 2 sites, 10 users, 23 menus, 248 dishes, 520 variants and validating zero cross-site/cross-tenant variant links. Original remains 0050 and SHA-256 **acf627a87ebb2bed9ec6521a982ea76bd1b3de53b3a8c11795fcef5e3b5de6f2**. 2,862 tests were collected, **not** run as one complete suite; old Task/metrics login fixtures still fail. No pilot or deployment approval.

**Pilot-minimal import protection:** persistent 0054 guard marks in_progress/completed/needs_review and blocks unsafe overlapping import/publication, without automated cross-store Saga or crash recovery. Manual needs_review handling is an operational gate. Do not claim full distributed atomicity or automatic rollback.

**Focus:** F08 → F09 → F10, then JWT RS256/F12–F15 in bounded risk-based gates. Fix real leaks, not speculative future features. Keep prior accepted A–Ö UI and Kitchen/Planera behavior frozen without reproduction. Release acceptance later needs full regression, a live multi-role walkthrough, provider reset end-to-end, new staging and backup/restore; historical Fly is not current development environment.

---


**Status:** Living engineering security baseline, reviewed 2026-11-22 (current overlay below; 2026-11-07 historical detail retained). This file records security controls and verified evidence; it does **not** grant pilot or production approval. The current release/gate authority remains [Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md). Do not add a competing MVP tracker here.

**Current verified product/security code checkpoint before docs-only commits:** `97c9cd6721f7a17b27de0e0f5650babf2cc81e12` — Gates 03H.5/03H.5B login recovery navigation and missing-HMAC test isolation, pushed 2026-11-07; prior login HTML fix `a8fed697` and reset expiry `c53b9452` also pushed. **Not deployed or hosted-live-verified.** The sole next-gate authority is `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md`.

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
| HTML login UX / CSRF | Gates 03H.2B and 03H.5B, browser acceptance and auth regression suite | **Code and isolated browser PASS:** Swedish HTML 401/429, Retry-After, unmodified JSON/API, globe and 390px viewport. New Forgot Password flow HTML POST **303 → login** with neutral flash and a back link, JSON remains **202**. **83 auth tests passed**. Owner confirmed ordinary correct local login and friendly wrong-password feedback; lockout/full recovery mail not yet owner accepted |
| Legacy session artifact | `cookie.txt` previously removed from Git index and added to ignore | **Incident still open** if session material appears in Git history; index removal does not revoke credentials or purge history |

### Transactional email provider: Postmark

- The user created and secured the Postmark account and saved a **dedicated transactional SMTP Access Key / Secret Key** outside Git. Credentials are never to be sent to Copilot, ChatGPT, CI logs, docs, test fixtures or commits.
- `yuplan.se`: Postmark DKIM and Return-Path verified; one.com standard SPF activated; DMARC TXT created as `v=DMARC1; p=none`. User-provided Postmark screenshot shows approval/live account. Provider configuration and **owner-confirmed SMTP inbox delivery** verified; this does not constitute hosted Yuplan password-reset mailer integration acceptance. DMARC aggregate reports are not set up; `p=none` requests monitoring rather than rejection.
- SMTP adapter settings for a later configured runtime (values are **not** secret material): `PASSWORD_RESET_SMTP_HOST=smtp.postmarkapp.com`, `PASSWORD_RESET_SMTP_PORT=587`, `PASSWORD_RESET_SMTP_SECURITY=starttls`, `PASSWORD_RESET_SMTP_FROM=no-reply@yuplan.se` (proposed). **Username = dedicated Postmark SMTP Access Key, password = dedicated SMTP Secret Key**; unlike Postmark's server API token variant, do not use the same token for both when separate SMTP keys are used.
- Other required environment variables: `PASSWORD_RESET_PUBLIC_BASE_URL` (actual public **HTTPS** URL of app, never marketing website), `PASSWORD_RESET_HMAC_SECRET` (separate strong secret), `AUTH_RATE_LIMIT_HMAC_SECRET` (separate), `PASSWORD_RESET_SMTP_USERNAME`, `PASSWORD_RESET_SMTP_PASSWORD`; optional timeout 10 seconds. Do not print their values.
- Gate 03G.1 **CLOSED**: env-based public reset URL fixed, code/test commit `7286fb64` pushed. Gate 03G.2 **POSTMARK DEVELOPMENT CLOSED / HOSTED ACCEPTANCE PENDING**: the adapter was not changed; Copilot added one explicit expiry-at-30-min regression in `tests/auth/test_password_reset.py`; **66 focused tests passed**, Ruff and diff check green. Owner ran controlled Python `smtplib` STARTTLS auth/send against Postmark port 587 with dedicated Access Key and Secret Key; Postmark accepted the email and the owner **confirmed receipt** at `info@yuplan.se`. No real Yuplan-app reset was exercised. **The expiry test was committed/pushed as `c53b945288fb832b4b388a39ee076e2f1dc600e4`.**
- Gate 03H.1 local-browser scenarios passed except a genuine HTML error-display UX defect (raw JSON). Gates 03H.2/03H.2B corrected HTML 401 and 429 to reuse the original Swedish Yuplan login template, preserved JSON/API, throttle and CSRF, and verified actual browser 401 → 401 → 429, Retry-After, post-lockout success and 390px mobile viewport. **82/82 auth tests and Ruff passed; code committed/pushed at `a8fed697826623513243036faa3efeab7a061b06`.** Owner manual UX review and hosted integration remain pending.
- The manually authorized standalone SMTP delivery smoke has passed. This proves real Postmark SMTP auth, submission and receipt, **not** hosted `POST /auth/forgot` recovery. An initial .NET `SmtpClient` attempt failed with `4.7.1 Relay access denied`; Python `smtplib` succeeds, and the application uses `smtplib`, so do not change the app mailer due solely to the .NET failure. Keep any reset tokens out of reports/logs. A Server API Token was visible in an earlier user screenshot and should be **rotated/revoked by the owner** (confirm rotation before closure of provider account security).

- **Local development environment recovered — Gate 03H.4 (2026-11-07):** an owner-observed login 503 was traced to missing local `AUTH_RATE_LIMIT_HMAC_SECRET` and SQLite schema version 0047 lacking the 0048/0049/0050 tables. With the local `run.py` server stopped, Copilot used SQLite backup API to make a verified pre-migration backup and successfully rehearsed an 0047→0050 migration on a disposable copy. Only then the ordinary local `instance/yuplan_mvp.db` was upgraded to 0050. Verified SQLite integrity `ok`, all four expected throttle/reset tables, and unchanged counts for six key data tables; wrote a dedicated HMAC secret into gitignored `.env` (no value exposed). Real local HTML login with a nonexistent test email now returns **401 with a user-friendly Swedish message**, not 503. Original database was **not** reset or reseeded, five protected dirty worktree paths untouched, no product code/commit/Fly changes. The backup file remains in Windows TEMP and should be copied to durable storage. **Owner subsequently confirmed successful local normal login and user-friendly HTML wrong-password feedback; full integrated real reset mail is still unaccepted.**

- **Gates 03H.5/03H.5B — CLOSED in code, user/hosted recovery still pending (2026-11-07):** one scoped correction to HTML Forgot Password redirects via HTTP 303 to `/auth/login` with neutral flashed status for both existing/nonexisting users, retaining a back link; JSON/API still returns 202 unchanged. An unrelated missing-HMAC negative-path test was made truly isolated via `monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_SECRET", "")` before app creation; **83/83 auth tests**, Ruff and diff check green. Four approved files were committed and pushed at **`97c9cd6721f7a17b27de0e0f5650babf2cc81e12`**; unrelated dirty work preserved. **Owner has not yet validated new 303 behavior on ordinary local browser; ordinary local app did not deliver an observed reset email.** Standalone Postmark SMTP credentials were successfully used in a separate direct smoke, but that does not verify their presence/configuration in Yuplan itself. Next audit local mailer env presence (never print secrets) and public URL/HTTPS safety, then perform a controlled owner-approved local integration test with separate account. Do not change main admin password just to test. Previously exposed Postmark Server API Token still needs rotation confirmation.

### Environment boundary / deployment hold

- **No new Fly deployment or changes to its secrets, volumes or DB are authorized during current Kommun 1.1 implementation.** This is a product-owner decision to avoid premature double work.
- The old Fly app `yuplan-unified-staging` was inspected read-only on 2026-11-07. Machine `68320edf664468`, volume `yuplan_data`, SQLite at `/data/yuplan_pilot.db`, startup mutations disabled. **DB migration current 0020, deployed migration head 0023**, while active development migration head is **0050**. The existing Fly installation is historical (not used for active Yuplan development for about 9–10 months), **not a candidate to upgrade blindly**.
- No backup, migration, deployment, secrets update or restart was performed. No staging or restore acceptance is claimed. Historical `docs/staging_postgres_runbook.md` references a **different, older Fly app** and must not be treated as the inspected SQLite app's actual runbook.
- After Kommun 1.1 is accepted locally, design a **fresh current-code staging environment**, rehearse DB schema and backup/restore on isolated data, set credentials as runtime secrets, verify real public HTTPS reset, throttling, cookies, account recovery and session revocation, then obtain product-owner pilot sign-off. This is later release work, not the current Copilot gate.

## Before Kommun pilot GO — outstanding security acceptance

1. **Local recovery delivery/integration remains pending; owner basic login is accepted.** Gates 03G.2, 03H.2B, 03H.5B are code/isolated-browser CLOSED, with current pushed code checkpoint `97c9cd67` and 83 auth tests passing. Owner confirmed normal local login + friendly wrong-password error. First run a read-only presence-only census of reset HMAC, SMTP settings and public reset URL (no secret output); then if settings are correct, obtain explicit owner approval for one real controlled test from the Yuplan app. Separately owner-verify new 303 flash/back link, lockout/unlock and mobile/iPad. Hosted full reset remains later acceptance. Confirm rotation of previously exposed Postmark Server API Token.
2. Reconcile historical session/cookie exposure, determine whether credential/session revocation is required, and ensure historical data is not inadvertently copied into a fresh pilot deployment.
3. Validate secure auth cookies, deployed auth/dev guards, API vs HTML login feedback, CSRF and rate-limit resilience on the **new release candidate**, not the historical Fly app.
4. Test cross-tenant/site/department denial, recovery token one-time/expiry, password reset impact on existing sessions/JWTs, and rollback/restore.
5. Complete live Kommun manual walkthrough, appropriate regressions and explicit release/freeze acceptance; green unit tests alone never imply pilot GO.

## Phased security maturity (not current pilot implementation)

- **Kommun pilot:** scoped auth/RBAC, secure cookies, distributed throttling, safe reset, backup/restore, deployment and tenancy checks.
- **Yuplan 1.0:** admin MFA, security events/alerts, secret scanning, vulnerability scanning, periodic independent review.
- **Larger enterprise customers:** SSO (e.g. OIDC), phishing-resistant passkeys, documented onboarding/offboarding and advanced access audit.

Threat-model and requirements reference: OWASP ASVS and relevant NIST identity guidance. These are target standards, not a claim of certification.
