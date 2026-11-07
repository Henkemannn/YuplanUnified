# Kommun 1.1 — Live Acceptance & UX Race


## CURRENT — 2026-11-07 — authoritative operational status

> This section is the **only current Kommun 1.1 delivery ledger**. The October baseline, older gate labels, and the September finishline paragraphs below/in other documents are historical evidence, not current orders. **No final Kommun 1.1 PILOT GO or Yuplan 1.0 release GO is claimed.**

**Active development branch:** `feat/planera-app-shell-2026-03-03`  
**Last confirmed pushed product/security checkpoint (before this documentation-only update):** `a8fed697826623513243036faa3efeab7a061b06` — `fix(auth): show user-friendly HTML login errors` (2026-11-07). Preceded by reset expiry regression checkpoint `c53b945288fb832b4b388a39ee076e2f1dc600e4`. Both commits are pushed and independently checked against GitHub; future docs-only commits advance remote ahead of the owner's local code checkout.  
**Last product-owner-approved visual UI checkpoint:** `1ff5dbef6336feac26943cafce09053ddc13dcd4`.  
**Worktree at last confirmed code checkpoint:** dirty with five unrelated protected paths: `core/admin_repo.py`, `scripts/seed_ostergarden_from_json.py`, `scripts/seed_product2_e2e.py`, `artifacts/`, `static/tests/builder_editor_host_styles.test.js`. Do not stage, overwrite or clean these. Documentation-only GitHub commits can advance the remote branch; reconcile with local HEAD **before future code commits**. Always check branch, HEAD, staged files and dirty paths; never assume remote HEAD equals the user's local HEAD.

**Status:** Kommun 1.1 remains under local development and final pilot acceptance. The user explicitly decided **finish Kommun 1.1 first, then prepare fresh staging/deploy**. Do **not** redeploy or migrate the old Fly installation as a shortcut. Keep completed UI/Builder/Planera/K25–K27 work frozen absent a reproduced regression.

### Product-owner-accepted / CLOSED scope

- **Builder Gates 19–21E (2026-11-05/06):** import/unresolved/manual Create Dish follows one atomic reviewed-create route; per-component reuse/new mode; category saved with Skapa rätt; common component parser supports spaced `&` and connective separators without splitting `R&B`. Checkpoints `f1195d17`, `1c926d90`, `f46da3c2`, `a75f754c`. Builder functional enhancement phase is frozen.
- **Planera 2.0:** Page1 → Page2 review → Page3 production underlag, normalkost/specialkost, primary/modifier, production completion and Weekview projections have been implemented and previously accepted for day-to-day pilot use. Do **not** reopen due to the September finishline's historical ACTIVE label.
- **K25–K27 (2026-10-31):** Kitchen Weekview compact serving-addon notes (`bbea233b`); Production Lists grouped by family with department quantity/comment and per-family/full printing (`b09c3d7a`); Page3 department packing list including standing addons and addon-only departments with print (`0d803262`). The 2026-11-06 code branch includes these commits. Packing/serving functionality is accepted, not an invitation to build a new engine.
- **Admin registered serving adaptations:** family-scoped reuse, no auto-select, Create New and duplicate warnings accepted (`ad96abd4`).
- **Kommun UI Gate 01 — Builder editor outer frame (2026-11-06): CLOSED.** The white/grey rectangular iframe background in Admin Menu Import was removed using a Kommun-host-only `color-scheme: normal` rule; product owner confirmed it disappeared after a hard reload. Shared Builder editor and Offshore untouched. Product checkpoint `3bfc98921959f29821da777e4e9375616594e84e`; 7/7 focused JS/host tests passed.
- **Kommun UI Gates 02B–02F.2 — Department Portal menu-choice visual recovery (2026-11-06): CLOSED for product-owner-approved desktop design in dark and light themes.** Repaired nested hidden week scrolling, theme token use, consistent 50/50 weekday lunch columns, separate full-width Dessert/Kvällsmat row, subtle day-card separation, and weekend Alt 1 + noninteractive single-option note in the Alt 2 position. Owner inspected the live authenticated page and approved the final visual result. Product checkpoint `1ff5dbef6336feac26943cafce09053ddc13dcd4`; 7/7 CSS layout/scroll/theme tests and 30/30 focused Portal Python tests passed. **iPad/mobile live visual walkthrough and actual choice/submit interaction remain release-acceptance checks**, not claimed closed here.
- **Account/site and role isolation foundations** previously implemented. Existing forced first-login change and `auth_version` revocation are not to be discarded when hardening login.

### Security and Postmark checkpoints (verified through 2026-11-07)

- **Login/deployed-mode guard:** the earlier Gate 03C.1 bypass precedence issue was corrected in code (`auth_bypass_allowed()` checks `FLY_APP_NAME` and deployed environments before the testing allowance). This is **code/test accepted, not a claim of deployed verification**.
- **Persistent login throttling:** implemented with database-backed account/IP throttles and reservation semantics (migrations 0048–0049). Preserve login/API behavior and `auth_version` revocation; actual hosted behavior not yet verified.
- **Self-service password reset:** implemented in code with hashed expiring single-use reset tokens, request-throttle storage (migration `0050_add_password_reset_storage`), anti-enumeration response and failure handling, and SMTP mailer adapter. Existing mailer uses authenticated TLS and requires an HTTPS reset URL. **Owner-confirmed real Postmark SMTP inbox delivery** and isolated browser reset lifecycle passed; **hosted/app-configured real email reset is still pending release acceptance**.
- **Password policy:** central validation `core/password_policy.py`, 15–1024 characters, Unicode/spaces supported, small explicit denylist with optional configured extension; legacy password logins must remain valid. Security code checkpoint `6caa9d1a51a24f7b5b8da6ad249ae227660f1903`.
- **Gate 03G.1 — CLOSED (2026-11-07):** `PASSWORD_RESET_PUBLIC_BASE_URL` now flows from environment through `Config.from_env()` into Flask config while explicit test overrides are preserved. Four changed files (`core/config.py`, `core/app_factory.py`, `tests/auth/test_password_reset.py`, `tests/auth/test_password_reset_mailer.py`); **79/79 auth tests green**, focused Ruff and `git diff --check` green; GitHub push confirmed at `7286fb64`.
- **Postmark account and DNS:** user verified Postmark approval and `yuplan.se` domain. Postmark DKIM and Return-Path verified; one.com SPF enabled and custom DMARC TXT `v=DMARC1; p=none` created. User generated and saved a **separate** Postmark SMTP Access Key / Secret Key outside Git/ChatGPT. Do **not** log, paste into Copilot, check in, or request their values. Proposed sender `no-reply@yuplan.se`; intended controlled recipient `info@yuplan.se`. Real SMTP delivery **confirmed by owner on 2026-11-07**; no hosted app reset claimed.
- **Gate 03G.2 — POSTMARK DEVELOPMENT CLOSED / HOSTED ACCEPTANCE PENDING (2026-11-07):** Copilot inspected the existing SMTP adapter without changing production code and added exactly one 30-minute token-expiry regression to `tests/auth/test_password_reset.py`. **66/66** focused reset/login/site-binding/revocation tests passed; Ruff and `git diff --check` passed on the local code checkpoint `7286fb64`. Owner ran a Python STARTTLS SMTP smoke on port 587 using the dedicated SMTP Access Key/Secret Key; console showed **SMTP login OK** and **Postmark accepted message** from `no-reply@yuplan.se` to `info@yuplan.se`; owner independently **confirmed receipt** in inbox. This was a standalone delivery smoke, **not** a valid reset token or complete hosted password-reset E2E. **Expiry regression was safely committed/pushed as `c53b945288fb832b4b388a39ee076e2f1dc600e4`**; hosted mailer and actual reset still require a fresh release candidate. The originally attempted .NET SMTP send got `4.7.1 Relay access denied`; the subsequent direct Python Postmark SMTP call succeeded, so no app-adapter redesign is justified. The owner also exposed an existing Postmark Server API Token in a screenshot; rotation/revocation needs owner confirmation before treating all account secrets as secure.

- **Gate 03H.1 — local browser acceptance (2026-11-07):** isolated browser test verified correct login/site/role, account/IP throttling, lockout and unlock, forgot/reset token lifecycle, invalidation of prior sessions/JWTs and the existing rotating globe. Found one real UX defect: HTML login errors rendered raw API JSON. No product files changed in the gate.
- **Gates 03H.2 / 03H.2B — HTML LOGIN UX CODE CLOSED / OWNER ACCEPTANCE PENDING (2026-11-07):** `core/auth.py` renders the existing Yuplan login page with generic Swedish 401/429 messages while preserving API JSON/status, Retry-After, CSRF, security controls and globe. Browser verified 401 → 401 → 429, Retry-After, success after unlock, destination and 390px viewport without horizontal overflow. **82/82 auth tests**, focused Ruff and diff checks green. Precisely two product/test files committed and pushed as `a8fed697826623513243036faa3efeab7a061b06`. No deployment or real owner login/reset walkthrough claimed. Five protected unrelated dirty paths remain unchanged.

- **Gate 03H.3/03H.4 — LOCAL AUTH RUNTIME RECOVERED (2026-11-07):** During first owner login acceptance on the ordinary local Yuplan at `127.0.0.1:5000`, HTML login returned `503 {"error":"service unavailable"}`. Read-only investigation proved the local database `instance/yuplan_mvp.db` remained at Alembic **0047** (missing auth throttling and reset tables), and local `.env` lacked `AUTH_RATE_LIMIT_HMAC_SECRET`. Following owner-authorized controlled recovery, Copilot stopped the server, verified the original SQLite integrity, created and verified a pre-migration SQLite backup outside Git, rehearsed migrations **0048→0050** on a copy, then migrated **only the local database** to **0050**. All four new tables exist; SQLite integrity `ok`; key entity counts remained tenants 1, sites 1, users 4, menus 13, departments 2, production_lists 0. A new dedicated strong rate-limit HMAC secret was placed in gitignored `.env` without displaying its value. Real local browser then returned **HTTP 401 `text/html` and Swedish friendly error** for one controlled nonexistent account attempt, not 503. No product-code, test-code, protected dirty files, Fly or Git changes; ordinary local server was stopped after the proof. **Owner manual normal-login, lockout and recovery acceptance is still pending**; standalone SMTP delivery and isolated reset browser acceptance are not full local Postmark integration. Backup currently under Windows TEMP (`yuplan-mvp-20261107-112122-backup.db`); preserve durable copy before relying on it.

### Fly inventory — historical environment, explicitly NOT the pilot-deploy target

The user confirms the existing Fly deployments were not used for active development for approximately **9–10 months**. Read-only inventory on 2026-11-07 found:
- Fly app `yuplan-unified-staging`, hostname `https://yuplan-unified-staging.fly.dev`, machine `68320edf664468`, release v141, health 1/1.
- Attached `yuplan_data` volume (~3 GB), runtime `DATABASE_URL` scheme SQLite, DB path `/data/yuplan_pilot.db`, `YUPLAN_ENABLE_STARTUP_MUTATIONS=0`.
- On-server Alembic **database current = `0020_add_diet_family_to_dietary_types`**; **deployed source head = `0023_scope_service_addons_by_site`**. Database approximately 1.2 MB with 48 tables; volume about 2.8 GB free. This is **not** the local migration HEAD `0050_add_password_reset_storage`.
- No backup, data migration, Fly secret setting, deployment or restart was performed during this inventory. No readiness/restore proof exists for the old DB.
- An older `yuplan-unified-staging-icy-wave-9332` environment and paused PostgreSQL apps also appear in Fly. Do not confuse old Postgres runbooks with the inspected SQLite app.
- **Decision:** leave all old Fly apps/data untouched. Do not advance the 0020 database to 0050 on the old machine. Once Kommun 1.1 reaches product-owner pilot acceptance, design a fresh, current-schema staging/release with proper backup, isolated migrations, runtime security and Postmark secrets verification.

### Next sequence — one Copilot order, one report, one review

1. **NOW: owner login/recovery acceptance after successful local schema/config recovery**, using a safe test account (or one controlled wrong-password attempt, then normal login to owner's own account). Local 503 is resolved by verified migration and environment setup; owner still needs to exercise login UX and reset.  Gates 03G.2 and 03H.2B are code/test CLOSED, but the owner has not personally exercised HTML login 401/429 lockout/unlock, forgot/reset, new-password login and UX at desktop/iPad. Do not run intentional lockout against a shared pilot/admin account. Isolated browser reset passed with captured fake mailer; provider SMTP delivery passed separately. Full integrated real reset through a configured deployed app is **hosted release acceptance**, not yet done. Preserve the accepted login globe. No deployment/migrations while Kommun 1.1 is under local development.
2. **Then resume remaining Kommun 1.1 release work** using product-owner-approved flows and actual defect evidence, not stale historical gate lists: clean-customer full walkthrough, admin/department/kitchen/portal/menu/Planera completion and persistence, report/export parity, negative tenant/site/RBAC, mobile/iPad acceptance, obsolete Portal JS fixture audit vs real bugs, HTML login feedback/CSRF and actual login UX with spinning globe preserved. A remaining item is closed **only** with reviewed evidence; do not reopen accepted work without reproduction.
3. **When Kommun 1.1 is actually accepted:** freeze/tag candidate; determine fresh staging/DB deployment strategy, safely rehearse and verify current migrations with backup/restore; stage Postmark secrets (separate SMTP Access Key = username, Secret Key = password; HMAC secrets separately), use actual app HTTPS reset URL, and perform hosted real reset/session invalidation/negative tests. New staging is a release-acceptance activity, **not** today's work.
4. **After Kommun 1.1 Pilot GO:** resume Offshore 1.0 then the cross-product Yuplan 1.0 release gate. See [Roadmap](roadmap.md).

**Important:** `docs/security/YUPLAN_SECURITY_BASELINE.md` tracks security controls, evidence and remaining risks; this file remains the sole operational next-gate authority. Neither doc-only updates nor passing auth tests imply a real deploy or pilot GO.

**Locked visual UI rule:** Product-owner accepted Kommun Builder modal and Department Portal Menyval must not be restructured or restyled by unrelated features. Any required change to an accepted screen needs explicit scoped approval, actual before/after browser evidence in both themes and relevant iPad viewport, plus focused regression tests. The existing CSS/DOM tests are useful but do not replace visual review. Historic approved screenshot baselines are not currently versioned in the repository; capture reviewed visual baselines during final pilot acceptance rather than falsely claiming pixel-snapshot coverage.

**Security baseline owner:** `docs/security/YUPLAN_SECURITY_BASELINE.md` records security controls, evidence and open security risks. This is not a separate product status ledger; the present Live Acceptance document remains the single operational gate authority.

### Known follow-ups: evidence, not automatic implementation orders

- **Reporting:** The October 31 investigation found several distinct report purposes and possible inconsistent coverage/export labels. At least one existing Weekview report already reads Product2 cohort completion truth; it is **not** accurate to say that every report is completely disconnected. A November 6 focused census showed 184 green non-report pilot tests, a report subset with 1 failure/3 errors and standalone Portal JS tests with 8 passing/11 failing; investigate test-harness drift vs real defects in the final verification. Review negative tenant/site/department report access and PDF/CSV/HTML consistency. Do not build a new reporting engine without an accepted concrete gap.
- **Menyval precedence:** Admin and Portal share canonical department choice persistence; October notes describe separate original/override/effective storage as not established. Preserve existing working choice flow; revisit precedence only when a concrete use case fails acceptance.
- **Portal JS test debt:** after visual checkpoint `1ff5dbef`, `static/tests/portal_department_week_choice.test.js` still reports **9 failures** using legacy `.portal-alt1-cell` / `.portal-alt2-cell` fixtures while the current template uses `button[data-choice-button]`. This is a suspected obsolete test fixture, **not yet formally closed**; examine its original behavioral assertions against the current ETag/choice/submit contract and fix test isolation or any proven product defect before final pilot GO. Preserve the visually approved screen.
- **Event and free menu contexts:** deferred until after Kommun pilot; do not alter weekly publication model to add Event now.

**Documentation governance:** `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md` owns current status. `docs/roadmap.md` owns phase sequence only. `docs/ground_truth/*` locks architecture/requirements, and their older checkpoint tables are historical snapshots. The separate `docs/kommun-status-review-2026-10-30` and `handoff/*` branches were used as evidence; do not use them as current task queues.

---


## Historical status (October 2026 baseline)

TECHNICAL AUTOMATED GATE = GO

LIVE ACCEPTANCE GATE 01 — CUSTOMER + SITE = GO

LIVE PILOT ACCEPTANCE = PENDING

## Historical baseline

- branch: feat/planera-app-shell-2026-03-03
- HEAD: 04731895afc290b7df4e65bdc15146f2f2b69daa
- 2342 passed
- 15 skipped
- 0 failed
- 3 warnings

## Gate 01 — Clean Customer + Site Onboarding

Status: GO

Manually proven:

- new customer creation
- new site creation
- separate customer Admin login in Firefox
- correct tenant/site context
- clean customer without leaked demo data
- persistence across separate session

## Historical Gate 02 — Departments + Needs

Status: IN PROGRESS

Reached:

- Admin → Avdelningar → Create Department → Department Edit

Department Edit is currently classified as a HIGH UX area and is paused for challenger work before final pilot acceptance.

Gate 02 is not GO yet.

## Section A — Clean Customer E2E

- [ ] New tenant/customer
- [ ] New site/kitchen
- [ ] New departments
- [ ] Resident/current quantities
- [ ] Requirement groups/needs
- [ ] Specialkost
- [ ] Serving adaptations
- [ ] Department login
- [ ] Builder menu import
- [ ] Resolve/build menu content
- [ ] Publish
- [ ] Kitchen Weekview
- [ ] Portal same menu
- [ ] Portal menu choices
- [ ] Explicit submit
- [ ] Portal→Kitchen propagation
- [ ] Planera lunch
- [ ] Planera kvällsmat
- [ ] Planera dessert
- [ ] Production underlag
- [ ] Completion propagation
- [ ] Report
- [ ] Persistence after reload/login

## Section B — Data Truth Assertions

Record these locks:

- Published Builder menu = canonical menu truth
- Department menu choice = canonical choice truth
- Registered needs/current quantities = business truth
- Portal = input/experience layer
- Planera 2.0 = production engine
- Weekview = operational projection
- No manual sync between Portal and Kitchen
- No second production/menu/choice truth

## Section B2 — Product Direction Locks

### Department Edit information model

Current recommended conceptual grouping:

- AVDELNINGEN
  - name
  - residence/facility relationship
  - baseline resident count
  - internal Department.notes / Faktaruta
- BEHOV
  - registered production-relevant needs
  - primary requirement
  - additional deviations
  - quantities
- SERVERINGSANPASSNINGAR
  - serving add-ons / adaptations
- VECKOVARIATIONER
  - varying resident counts
  - other genuinely week/day-specific operational exceptions

Requirement-group is a backend/domain term only; normal Kommun admins should not need to learn that term in the final UI.

### Department Edit UX findings

- UX-13 HIGH: Department Edit lacks a clear mental model/hierarchy.
- UX-14 HIGH: Multiple independent save actions make save scope unclear.
- UX-15 HIGH: Specialkost and Registrerade behov overlap semantically in the UI even though they represent different domain concepts.
- UX-16 HIGH: Requirement-group terminology is too technical for normal Kommun admin.
- UX-17 MEDIUM/HIGH: Serveringstillägg is presented as a technical row editor instead of clear operational information.
- UX-18 MEDIUM: Department list provides weak operational differentiation/status.

### Menu choice direction

The menu-choice operational workflow should not primarily live inside Department Edit.

Preferred primary surface for Kommun 1.1:

- Admin → Menyval

MVP scope:

- choose/view a published week
- show all departments
- status per department: Klar, Delvis klar, Ej påbörjad
- simple filter/segmented control: Alla, Behöver åtgärd
- show the days where a real menu choice is required
- show the department's current choice
- allow admin to change a department's menu choice
- after save, return naturally to the overview

Deferred from Kommun 1.1:

- push/reminder sending
- choice analytics
- popularity statistics
- historical dashboards
- raw-material forecasts
- generic cross-vertical choice analytics
- new statistics engine

### Admin override technical gate

Product intent:

- An admin/kitchen change is authoritative.
- If Admin changes a department choice, the effective production choice must follow the admin decision.

Current implementation note:

- Portal and Admin currently write into the same canonical department_menu_choices truth.
- The current implementation does not yet preserve three separate persisted concepts for original Portal choice, Admin override, and effective choice.

This is an open technical gate and must be revisited before implementing Admin → Menyval at full scope.

## Section C — UI/UX Race

For every major screen capture record:

- route/screen
- screenshot/reference
- task user is trying to complete
- friction
- severity: BLOCKER / HIGH / MEDIUM / LOW
- recommended action
- accepted/fixed/deferred

Initial screens to inspect:

1. Customer creation / onboarding
2. Site/kitchen setup
3. Departments list
4. Department create
5. Department detail
6. Department edit

Known concern:

Department edit is known to be visually and interaction-wise messy and requires serious UX review.

Then:

7. Needs / requirement-group administration
8. Builder import
9. Builder unresolved flow
10. Dish editor
11. Component editor
12. Publish flow
13. Kitchen Weekview
14. Planera entry/day overview
15. Planera review
16. Produktionsunderlag
17. Department Portal Home
18. Department Portal Week
19. Reports

Accepted product privacy distinction:

- Department-facing structured fact area stays visible to unit_portal.
- Department.notes / internal Faktaruta is private and must never render to unit_portal.

The privacy defect on the old compatibility Portal week surfaces was closed in commit 04731895afc290b7df4e65bdc15146f2f2b69daa.

UX principle:

Do not redesign everything blindly. First walk the real task, then screenshot, then identify friction, then challenge or redesign only where justified.

Tablet/iPad-first remains a core acceptance lens.

## Section D — Release Blockers

Only BLOCKER and HIGH issues can stop pilot unless the project lead decides otherwise.

| ID | Area | Finding | Severity | Owner | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |

## Section E — Release Exit Criteria

Kommun 1.1 may become final PILOT READY only when:

- clean-customer chain passes
- lunch/kvällsmat/dessert Planera requirement is verified or an explicit product decision is made
- Portal and Kitchen show the same canonical publication and choices
- tenant and department scoping is proven
- no blocker-level UX failure remains
- accepted UX fixes are regression-tested
- final automated suite is green after any product changes
- pilot candidate HEAD is frozen/tagged

Current release sequence:

1. Gate 02 — Departments + needs
2. Department Edit UX challenger
3. Admin menu-choice technical semantics gate
4. Thin Admin → Menyval overview if implementation remains small
5. Continue clean-customer live E2E: published menu, Portal choices, Kitchen propagation, Planera, Produktionsunderlag, completion, Reports, persistence/relogin
6. UX race fixes
7. Final regression
8. Freeze/tag Kommun 1.1
9. Offshore 1.0

## Notes

This document is the working ledger for the live acceptance phase and the UX race.

The live acceptance status above reflects the manually proven customer/site onboarding gate and the currently paused Department Edit / department needs work.
