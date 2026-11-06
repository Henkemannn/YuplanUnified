# Kommun 1.1 — Live Acceptance & UX Race


## CURRENT — 2026-11-06 — authoritative operational status

> This section is the single current Kommun 1.1 pilot work ledger. The October baseline, older gate labels and old recommended sequence lower in this document are **historical**. Never use those older labels to reopen work already accepted by the product owner. Not a claim of full pilot/release GO.

**Development branch:** `feat/planera-app-shell-2026-03-03`  
**Last product-code checkpoint pushed and product-owner approved:** `1ff5dbef6336feac26943cafce09053ddc13dcd4` (2026-11-06; `fix(portal): restore department menu choice layout and theme`). Subsequent docs-only commits may advance the branch HEAD; use `git rev-parse HEAD` for every preflight.  
**Worktree:** locally dirty; protected, unrelated edits must remain untouched: `core/admin_repo.py`, `scripts/seed_ostergarden_from_json.py`, `scripts/seed_product2_e2e.py`, `artifacts/`, `static/tests/builder_editor_host_styles.test.js`. Verify current local state before every Copilot order.

**Status:** Kommun 1.1 pilot preparation; **NOT YET final PILOT GO**. Product-owner-accepted operational features are frozen except for reproducible regressions.

### Product-owner-accepted / CLOSED scope

- **Builder Gates 19–21E (2026-11-05/06):** import/unresolved/manual Create Dish follows one atomic reviewed-create route; per-component reuse/new mode; category saved with Skapa rätt; common component parser supports spaced `&` and connective separators without splitting `R&B`. Checkpoints `f1195d17`, `1c926d90`, `f46da3c2`, `a75f754c`. Builder functional enhancement phase is frozen.
- **Planera 2.0:** Page1 → Page2 review → Page3 production underlag, normalkost/specialkost, primary/modifier, production completion and Weekview projections have been implemented and previously accepted for day-to-day pilot use. Do **not** reopen due to the September finishline's historical ACTIVE label.
- **K25–K27 (2026-10-31):** Kitchen Weekview compact serving-addon notes (`bbea233b`); Production Lists grouped by family with department quantity/comment and per-family/full printing (`b09c3d7a`); Page3 department packing list including standing addons and addon-only departments with print (`0d803262`). The 2026-11-06 code branch includes these commits. Packing/serving functionality is accepted, not an invitation to build a new engine.
- **Admin registered serving adaptations:** family-scoped reuse, no auto-select, Create New and duplicate warnings accepted (`ad96abd4`).
- **Kommun UI Gate 01 — Builder editor outer frame (2026-11-06): CLOSED.** The white/grey rectangular iframe background in Admin Menu Import was removed using a Kommun-host-only `color-scheme: normal` rule; product owner confirmed it disappeared after a hard reload. Shared Builder editor and Offshore untouched. Product checkpoint `3bfc98921959f29821da777e4e9375616594e84e`; 7/7 focused JS/host tests passed.
- **Kommun UI Gates 02B–02F.2 — Department Portal menu-choice visual recovery (2026-11-06): CLOSED for product-owner-approved desktop design in dark and light themes.** Repaired nested hidden week scrolling, theme token use, consistent 50/50 weekday lunch columns, separate full-width Dessert/Kvällsmat row, subtle day-card separation, and weekend Alt 1 + noninteractive single-option note in the Alt 2 position. Owner inspected the live authenticated page and approved the final visual result. Product checkpoint `1ff5dbef6336feac26943cafce09053ddc13dcd4`; 7/7 CSS layout/scroll/theme tests and 30/30 focused Portal Python tests passed. **iPad/mobile live visual walkthrough and actual choice/submit interaction remain release-acceptance checks**, not claimed closed here.
- **Account/site and role isolation foundations** previously implemented. Existing forced first-login change and `auth_version` revocation are not to be discarded when hardening login.

### Decided remaining order — one gate at a time

1. **NOW — Login and password recovery.** Audit current login, failed-attempt rules, HTML feedback, lockout persistence across workers, password-recovery email/token (expiry, one use, anti-enumeration), password change/reset, role routing, revocation/session invalidation, tenant/site scope, audit events and browser/iPad handling. Confirm what is already implemented before changing anything. Preserve the spinning Yuplan globe. Existing `/auth/forgot` was documented as a placeholder on 2026-11-01, not assumed complete.
2. **THEN — Product-owner full manual Kommun walkthrough** combined with isolated automated and negative tenant/site/RBAC regressions, real Portal choice/submit and kitchen propagation, critical desktop/iPad/mobile screens, reporting/export consistency and lunch/kvällsmat/dessert meal paths. Fix only reproduced issues.
3. **THEN — Pilot acceptance, release verification and freeze/tag.** Confirm clean-customer path, staging/migrations, full appropriate regression and security; no unverified blanket GO.
4. **AFTER KOMMUN — Offshore 1.0**, then Yuplan 1.0 platform release.

**Locked visual UI rule:** Product-owner accepted Kommun Builder modal and Department Portal Menyval must not be restructured or restyled by unrelated features. Any required change to an accepted screen needs explicit scoped approval, actual before/after browser evidence in both themes and relevant iPad viewport, plus focused regression tests. The existing CSS/DOM tests are useful but do not replace visual review. Historic approved screenshot baselines are not currently versioned in the repository; capture reviewed visual baselines during final pilot acceptance rather than falsely claiming pixel-snapshot coverage.

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
