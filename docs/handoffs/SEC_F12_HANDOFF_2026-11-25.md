# YUPLAN UNIFIED – SEC-01 / F12 handoff (2026-11-25)

> **CURRENT HANDOFF**. This document is for a new ChatGPT project-lead conversation. It lives on the documentation-only branch **handoff/sec-f12-2026-11-25**. The active development branch is **feat/planera-app-shell-2026-03-03**; NEVER use the handoff branch for product development. Source checkpoint: **7df6f8534b529359abee626c914f9c159d2bbdef**. Older CURRENT sections in underlying documents are historical until a deliberate docs sync.

## FIRST ACTION IN NEW CHAT – NON-NEGOTIABLE

The owner has just sent Copilot the order **SEC-F12-AUDIT-01** (read-only support authorization audit). **The new chat must first receive and read the resulting Copilot report.** Review the actual results and decide whether F12 can be scoped-closed or requires a narrow fix. Do NOT issue another F12 audit or a new development task before examining that report. If the report is not yet attached, request only the report. Do not invent audit findings. Then follow **one order → one Copilot report → independent project-lead review → guarded commit/push → next order**.

## GIT AND DATABASE CHECKPOINT

- Repository: **Henkemannn/YuplanUnified**
- Product branch: **feat/planera-app-shell-2026-03-03**
- Verified GitHub product HEAD: **7df6f8534b529359abee626c914f9c159d2bbdef** (SEC-JWT-ALG-02, 2026-11-25); user's terminal reported local + remote match and **Git CLEAN**. Any subsequent Copilot reports must verify their own checkpoint.
- Product source must remain at 7df6f8534b529359abee626c914f9c159d2bbdef while the read-only F12 audit is running. Documentation updates in THIS branch must NOT be fast-forwarded/merged into the active product branch during the ongoing audit. Never reset or checkout over dirty work.
- Protected original SQLite: **instance/yuplan_mvp.db**; protected backup: **C:\Users\Henrik Jonsson\YuplanPilotBackups\yuplan_mvp_20261123_135608.db**. Each expected SHA256: **1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67**. Verify before/after any gate. No mutation, migration, seeding, copying into share packages or reading real pilot rows. Use isolated synthetic/temp SQLite.
- Project Python: **.venv\Scripts\python.exe** (Python 3.11.9), use explicit executable. An empty VIRTUAL_ENV alone is not evidence of a broken venv.
- Old Fly deployment is ~6 months behind: NOT a valid current staging/pilot validation. No deploy/migrate/pilot GO authorized.

## SECURITY STATUS – AS OF HANDOFF

| Work | Status | Evidence / limit |
|---|---|---|
| SEC-F01–F09 | Scoped CLOSED in audited paths | Includes F08 report/export guard and F09 tenant/site Planera checks; no blanket authorization certification |
| SEC-F10 | Scoped CLOSED | Anonymous demo synthetic checks; 9 permanent regression identities; 51 targeted PASS; not live-hosted proof |
| SEC-F11 | **Code/scoped CLOSED**, real-runtime OPEN | Central fail-closed environment/secret fallback across config, factory, auth, Bearer; commit **d3d6cb8a1e3ba317e5c6ee757832f5dbd9e92251**; 90 targeted PASS. Current staging secret injection/startup/cookies must be verified later |
| SEC-JWT-ALG-02 | **Code/scoped CLOSED** | Commit **7df6f8534b529359abee626c914f9c159d2bbdef**; only HS256 verification, rejects RS256/HMAC, removes secondary landing Bearer authentication. Red reproduction: RS256-HMAC accepted; refresh-token on '/' set session; both rejected after fix. 80 targeted PASS; runtime proof still pending |
| SEC-F12 | **IN PROGRESS – read-only report pending** | Support access authorization and sensitive logs; new chat's FIRST action is to review SEC-F12-AUDIT-01 Copilot report |
| SEC-F13 | OPEN P1 | Upload size/bounds/failure handling |
| SEC-F14 | OPEN P1 | Temporary password displayed/flashed in UI |
| SEC-F15 | OPEN P1 | Unsafe Weekview schema mutation/repair during requests |
| Whole-suite + staging + pilot acceptance | OPEN | No full pytest since F10 and later F11/JWT code changes; active staging/real roles/golden path, HTTPS/cookies, reset, backup/restore, migration review outstanding |

Most recent **full isolated pytest** was **HEALTH-12R**, source HEAD **46277ded13cc66d4a8b67add5b94c7786618fafa**: **3,018 collected / 3,003 PASS / 0 FAIL / 0 ERROR / 15 SKIP**, exit 0. This predates F10's 9 tests and F11/JWT changes. Full pytest takes ~19–47 minutes and should run at a meaningful security checkpoint, not each gate; compare JUnit identities.

## SEC-F12-AUDIT-01 – EXACT TASK IN FLIGHT

Read-only review, no code changes, no new repository tests, no full pytest. Check Git clean + product HEAD 7df6f8534b529359abee626c914f9c159d2bbdef + both DB hashes. Analyze **core/support.py**, **core/app_authz.py**, **core/logging_setup.py**, **core/app_factory.py**, **tests/test_support.py**, **tests/test_support_ui.py**, relevant impersonation/real-auth tests.

Registered diagnostic endpoints:
- GET **/admin/support/**
- GET **/admin/support/lookup**
- GET **/admin/support/ticket/<rid>**
- GET **/admin/support/ui**

All currently decorated **@require_roles("superuser")**. Existing tests rely partly on **X-User-Role/X-Tenant-Id** test-only headers; therefore inspect **genuine login/session and valid Bearer JWT** with synthetic users, not only testing header stubs. Test anonymous, cook, department, site-admin, other-tenant admin, inactive/revoked user, stale auth-version, legit system superuser, tampered identity/tenant/site, Bearer wrong role, all four routes. Verify LOG_BUFFER's global warnings and disclosure of other-tenants' data/secrets. Inspect support UI's dynamic **innerHTML** rendering of log fields as a **potential unconfirmed injection issue**, separately from route authorization. Do not present it as a proven exploit without reproduction.

Project policy: tenant=customer, site=workplace; ordinary user bound to exactly one validated site through account (no site picker/switch, missing binding fail-closed). Customer/site admin can NEVER elevate to system superuser; support is a separately authorized system role. A passing @require_roles decorator alone does not prove that every session/cookie/header flow is safe.

**On receiving F12 report:** 1) verify checkpoint and test methodology; 2) distinguish reproduced issue vs theoretical; 3) independently check actual GitHub code if needed; 4) decide scoped close vs SEC-F12-FIX-01; 5) no commit without concrete review of the exact diff. Use bounded targeted regression only.

## PROCESS AND NEXT GATES

- One Copilot order, one returned report, independent security review, narrowly scoped corrections only when reproduced, reviewed ZIP for consequential security changes, guarded PowerShell commit and push; verify new GitHub HEAD after pushing.
- Do not run full pytest routinely. F12 → F13 → F14 → F15, then reconcile security scope, run broad/full regression checkpoint, live role/site walkthrough, fresh staging verification and release acceptance.
- Product is Flask + SQLAlchemy + Alembic/SQLite pilot. Strict tenant isolation throughout Builder/imports/dishes/menus; no cross-tenant reuse, no ordinary user site-switch. Keep previously owner-accepted Kommun 1.1 A–Ö UI frozen unless a fresh reproducible regression exists.
- Finish SEC before returning to Kommun 1.1 A–Ö. Separate systemadmin/support from customer admin; don't accidentally broaden roles.
- GitHub docs files **docs/security/YUPLAN_SECURITY_BASELINE.md** and **docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md** are updated with a latest overlay on THIS handoff branch. Historical sections below remain factual history, not active next-gate instructions.
- Never confuse “code/scoped CLOSED” with deployed secure / municipality pilot GO. No old Fly redeployment, current pilot DB migration, or staging acceptance without explicit owner release decision.
