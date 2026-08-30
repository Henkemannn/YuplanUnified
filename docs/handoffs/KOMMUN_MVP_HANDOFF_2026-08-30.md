# Yuplan Unified — Kommun MVP handoff

**Date:** 2026-08-30  
**Purpose:** engineering/project-lead handoff to a new ChatGPT/Copilot session while the active local worktree is dirty and Copilot is executing `KOMMUN-MENU-E2E-6D`.

> This is a **checkpoint**, not a finished-state document. The latest Copilot 6D report must be read together with this file. If the report conflicts with the pre-6D RED state below, the newer verified result wins.

---

## 1. Repository, active branch and safe handoff branch

Repository:

`Henkemannn/YuplanUnified`

Active local development branch:

`feat/planera-app-shell-2026-03-03`

GitHub remote tip of that branch at handoff time:

`2817aaf16c2d85e914f37f7dd5dee856436af117`

Commit message:

`docs: lock cross-domain portal foundation`

Relevant previous frozen commit:

`d8c316a75f503b5c785c333fe774410936e5d607`

Commit message:

`feat(portal): cut unit portal over to canonical department portal`

This handoff document is intentionally stored on a separate documentation-only branch:

`handoff/kommun-mvp-2026-08-30`

Reason: the user's local active feature branch has an intentionally dirty worktree and Copilot is in the middle of a correction ticket. Writing directly to the remote active branch would create a remote commit ahead of the user's dirty local branch and complicate the in-flight work. **Do not switch local development to the handoff branch.** Continue development on `feat/planera-app-shell-2026-03-03`.

At handoff time, GitHub remote for the active feature branch is still at `2817aaf`. The uncommitted local changes from E2E-3/4/6B/6C/6D are therefore **not visible on GitHub yet**. The exact current local `git status --short` must come from the latest Copilot report/user terminal, not from this document.

---

## 2. Project-lead operating mode

The assistant acts as project lead/work leader. Do not broaden scope or perform large refactors because something adjacent looks untidy.

Working style:

- Keep one bounded ticket at a time.
- Give GitHub Copilot in VS Code explicit copyable instructions.
- User runs cheap Git/pytest commands manually in PowerShell when useful.
- If a gate fails, fix that gate before moving on.
- No reset/revert/stash of intentional dirty work unless explicitly agreed.
- Do not commit until the current canonical menu/publication/portal block is verified in real browser + tests.
- Preserve existing Kommun behavior unless a verified bug or architecture cutover requires a change.
- MVP first; unrelated polish goes to backlog.

Main practical finishline now:

`Portal/information chain -> canonical menu-choice truth -> Planera 2.0 Kommun -> bounded polish -> full E2E -> Kommun Ready for Pilot -> Offshore 1.0`

---

## 3. Locked architecture

Yuplan data ownership direction is locked:

- **Builder** owns canonical menu knowledge.
- **Canonical publication** is immutable published menu truth.
- **Kommun / Offshore** provide business context.
- **Planera** consumes canonical business/menu truth and calculates production.
- **Portals** are communication/experience layers; they must not become parallel data authorities.

Required dependency direction:

```text
canonical/shared menu source
        |
        +--> Kommun Weekview
        +--> Kommun Menyoversikt
        +--> Dashboard
        +--> reports / planning consumers
        +--> Department Portal independently
        +--> future Planera 2.0
```

Forbidden architecture:

```text
Department Portal -> Kitchen Weekview
Kitchen Weekview -> Department Portal
Dashboard -> Department Portal
```

A Portal service may consume shared/core truth. Core kitchen services must not use a Portal application service as their data source.

Core business principle:

> **One business fact = one canonical truth. Many authorized functions may read it; authorized writers may update the same truth, but there must not be drifting parallel copies.**

The Kommun module is otherwise largely functional. Do not rebuild it. The current work is integration/stabilization around canonical truth.

---

## 4. Portal Foundation / P2A — finished and frozen

P2A was completed and committed at:

`d8c316a feat(portal): cut unit portal over to canonical department portal`

Verified behavior:

- `unit_portal` login -> canonical `/ui/portal/department/week`
- `staff` -> old `/ui/portal/week` unchanged
- `department` -> old `/ui/portal/week` unchanged
- admin/kitchen/superuser unchanged
- unit portal cannot enter `/ui/admin`
- unit portal navigation is scoped appropriately
- canonical header uses ISO week/date span

Full suite after P2A:

`1803 passed, 15 skipped, 3 warnings, 0 failed`

Cross-domain Portal Foundation lock was then merged in:

`2817aaf docs: lock cross-domain portal foundation`

Important Portal Foundation decision:

- shared/potentially shared: scoped identity/auth, published menu consumption, week/day context, explicit choices/confirmations, status/progress, reminders/communication, responsive shell
- Kommun-specific: Department scope, residents/resident counts, Kommun dietary context, explicit department menu choices
- Offshore later must reuse shared Portal Foundation through its own Offshore adapter/context
- do not prematurely generalize valid domain-specific models

---

## 5. Real Kommun test environment

Manual test environment used for current E2E:

```text
Tenant:       Primary
Site:         KommunTestA
Boende:       Testgarden
Avdelning:    Avdelning A
Boendeantal:  10
```

Unit portal test account:

```text
Username:   TestpersonalAvdA
Role:       unit_portal / Enhetsportal
Department: KommunTestA / Avdelning A
Status:     active
```

Scope chain:

```text
User.department_id
-> Department.site_id
-> Site.tenant_id
```

Test menu:

`2026-W35`

CSV shape:

`Year,Week,Weekday,Meal,Alt,Text`

28 rows = 7 days x Alt1 / Alt2 / Dessert / Kvallsmat.

Important Monday values:

- Alt1: `Kottbullar med graddsas och potatis`
- Alt2: `Ugnsbakad lax med dillsas och potatis`
- Dessert: `Appelpaj med vaniljsas`
- Kvallsmat: `Tomatsoppa med ostsmorgas`

Important Sunday evening value:

- Kvallsmat: `Kottfarspaj med sallad`

(The live Swedish database/UI text contains the proper Swedish characters; ASCII is used here only where practical in the engineering handoff.)

---

## 6. Canonical menu import/publication — original root cause and current direction

Original real E2E failure:

Admin imported/published a week, but Department Portal showed no menu.

Root cause was proven:

**legacy menu was published, but canonical Builder link/publication was missing.**

Old CSV import created legacy `Menu` / `MenuVariant` data only. It did not create the required Builder menu/link/pin. The old publish path could mark the legacy menu published while canonical publication returned `None`.

Department Portal is canonical-only, so it correctly showed no menu when there was no canonical publication.

E2E-3 direction:

```text
legacy-compatible admin CSV import
+
canonical Builder menu/projection
+
Commun Builder link
+
fail-closed canonical publication
```

Important invariants:

- no Portal fallback to private/legacy menu data
- no fake Components/Compositions for unresolved imported menu text
- import must remain idempotent
- publication is fail-closed
- if canonical link/publication cannot be established, legacy menu must not be treated as successfully published

Manual real-browser verification after the canonical import fix:

- import W35 -> canonical menu/link created
- publish -> Department Portal receives menu
- unpublish -> menu disappears from Department Portal
- republish directly, without re-import -> menu returns

This publish/unpublish/republish behavior is considered **GREEN** for menus that passed through the new canonical import path.

Do not reopen the historical pre-fix W35 republish issue as a current bug.

Choice rows are intentionally not deleted on temporary unpublish.

---

## 7. Department Portal menu-choice persistence — fixed and green

Original browser bug:

The UI appeared to turn Alt1/Alt2 green, but progress remained `0/7` and reload removed the choices.

Root cause:

Browser sent Swedish display weekday values such as `Mandag`, while API expected canonical codes:

`mon/tue/wed/thu/fri/sat/sun`

The UI also painted green optimistically before confirming server success.

Correction:

- explicit Swedish display weekday -> canonical code mapping in browser
- green success state only after HTTP success
- progress/dots update after successful persistence
- reload derives state from persisted data

Manual result is **GREEN**:

- explicit choices persist
- green state persists
- progress X/7 works
- reload retains choices

Canonical current table:

`department_menu_choices`

Semantics:

```text
None = no explicit choice
Alt1 = explicitly chosen Alt1
Alt2 = explicitly chosen Alt2
```

Critical rule:

> **No choice is not the same as Alt1.**

---

## 8. Canonical Alt1/Alt2 single-truth direction — discovered, NOT implemented yet

A read-only audit found three currently live stores:

1. `weekview_alt2_flags`
2. `alt2_flags`
3. `department_menu_choices`

Legacy stores are used by old Kommun operational flows.

Known writers/readers include:

- kitchen Weekview operational Alt2 writer/readers
- admin/planning Alt2 writers
- Department Portal explicit choice writer
- dashboard/overview readers
- reports/statuses
- current Planera 1.0 production flow

Important product decision:

`department_menu_choices` should become the canonical explicit current department meal-choice truth.

Authorized writers:

- Department Portal
- `Admin -> Avdelning -> Andra menyval`

Admin is not a separate override truth. Admin is another authorized writer to the same canonical current choice.

Example:

```text
Department chooses Monday Alt1
-> admin changes Monday to Alt2
-> canonical current choice is Alt2
-> Portal, Weekview, reports, Planera all read Alt2
```

Existing kitchen UX must remain:

- explicit Alt2 -> yellow day/cell state
- change to Alt1 -> yellow state disappears

Planera 1.0 already consumes Alt2-derived information in production lists. Therefore the future Alt1/Alt2 cutover must include Planera 1.0 and cannot be treated as a Portal-only UI change.

**Do not implement this cutover until the current menu/publication/read-chain block is stable and committed.**

---

## 9. Kvallsmat / dinner_main — confirmed canonical data chain

The evening menu data itself is not missing.

Confirmed import/publication chain:

```text
CSV evening row
-> legacy meal=Kvall / variant=kvall
-> canonical bridge dinner_main
-> Builder projection meal=dinner / variant=main
-> canonical publication snapshot
```

Canonical publication contains the evening meal.

Department Portal can display the evening meal.

Thus the live defect is in older/shared Kommun kitchen read paths and normalization, not in publication data loss.

Important internal/display terminology split:

```text
Builder/internal: dinner / main / dinner_main
Kommun presentation: Kvallsmat
```

Do not globally rename Offshore/shared terminology.

Expected real W35 evening examples:

- Monday: `Tomatsoppa med ostsmorgas`
- Sunday: `Kottfarspaj med sallad`

---

## 10. 6B architecture correction

An early 6B attempt made `core/weekview_vm.py` call `portal.department.service.build_department_week_payload()` because the Portal already knew how to read canonical dinner/main.

That approach was rejected.

Reason:

```text
WRONG:
Portal service -> core Weekview VM
```

Portal is an application consumer, not a shared data source. It also risks circular layering because Portal itself consumes Weekview facts.

Locked direction:

```text
shared/core menu read model -> Weekview
shared/core menu read model -> Dashboard
shared/core menu read model -> Menyoversikt
shared/core menu read model -> Portal independently
```

Any new `core/weekview*` dependency on `portal.department.*` must be rejected.

---

## 11. 6C report versus real browser verification

Copilot 6C reported a core DB-backed read approach using `MenuServiceDB`, with focused tests green.

Reported claims included:

- Weekview route 200
- dashboard evening resolved
- Kommun label `Kvallsmat`
- focused pytest green
- Offshore guard green

However, real manual browser verification after that report showed:

- **Kitchen Weekview still returned HTTP 500**
- **Kitchen Menyoversikt still showed `Kvallsmat: -` for every day**

This proves the narrow focused tests did not cover all real kitchen paths.

Do not accept a future statement like `Weekview is green` unless actual kitchen Weekview tests and real browser path are covered.

---

## 12. Current RED state immediately before 6D

Manual browser state before 6D:

### Green

- canonical CSV import
- canonical Builder link
- canonical publication
- unpublish
- republish without re-import
- Department Portal publication visibility
- Department Portal menu content
- Department Portal evening meal
- Department Portal explicit Alt1/Alt2 persistence
- progress 7/7

### Red

#### Kitchen Weekview

Still returns HTTP 500.

Observed wrapper:

```text
detail: internal_error
status: 500
incident_id: 4fbf75f4-f3ab-4b76-b1d4-8aa719dfa0a5
request_id: fa3cc995-e180-416a-b023-3d31144c3074
```

The real traceback/root cause must be captured; do not guess from the RFC7807 wrapper.

#### Kitchen Menyoversikt

For W35, lunch Alt1, lunch Alt2 and dessert are visible, but every day shows:

`Kvallsmat: -`

Even though canonical publication and Department Portal contain the evening values.

#### Dashboard

Earlier manual screenshots showed current-day dashboard row:

`Kvall -`

Copilot attempted to correct dashboard normalization/label in 6C, but the entire kitchen read chain is not considered green until 6D + manual browser verification.

---

## 13. Latest full pytest before 6D

User ran full suite after 6C.

Result:

```text
17 failed
1788 passed
15 skipped
3 warnings
```

Failing tests:

```text
tests/admin/test_admin_ui_menu_import_phase9.py::
test_week_view_renders_imported_dishes_for_2026_w11

tests/core/test_commun_builder_projection.py::
test_projection_reader_duplicate_comparison_detects_missing_in_legacy

tests/core/test_commun_builder_projection.py::
test_shadow_mode_preserves_legacy_response_and_records_comparison

tests/ui/test_kitchen_planering_uses_menu_utils_titles.py::
test_planering_uses_menu_utils_titles_prefers_main_over_alt1

tests/ui/test_kitchen_veckovy_grid_mode.py::
test_kitchen_grid_renders_and_icons_present

tests/ui/test_kitchen_veckovy_grid_mode.py::
test_cell_classes_markerad_and_alt2

tests/ui/test_kitchen_week_menu_modal.py::
test_kitchen_week_has_shared_menu_modal

tests/ui/test_kitchen_week_v3.py::
test_kitchen_week_v3_renders_and_flags

tests/ui/test_kitchen_week_v3.py::
test_kitchen_week_v3_mark_toggle

tests/ui/test_kitchen_week_v3.py::
test_kitchen_week_v3_default_select_premarked_cells

tests/ui/test_kitchen_week_v3.py::
test_kitchen_week_v3_default_select_false_not_premarked_cells

tests/ui/test_kommun_core_flow_phase1.py::
test_end_to_end_department_choice_to_weekly_report

tests/ui/test_portal_department_week_flow_phase1.py::
test_portal_department_week_choice_happy_path

tests/ui/test_portal_department_week_flow_phase1.py::
test_portal_department_week_choice_persists

tests/ui/test_unified_weekview_department_choices_phase2.py::
test_weekview_reflects_department_registration_choice

tests/ui/test_weekview_report_phase3_marks.py::
test_weekview_report_phase3_debiterbar_marks

tests/ui/test_weekview_report_ui_phase1.py::
test_weekview_report_basic_structure
```

Observed failure classes:

### A. Real kitchen runtime regression

Several `test_kitchen_week_*` routes return 500. This aligns with the real browser failure.

### B. Missing evening/Kvallsmat in kitchen read chain

Canonical publication is correct, but kitchen consumers are not all receiving the normalized standard evening slot.

### C. `canonical_publication_missing`

Several older tests/flows now fail because fail-closed publication requires canonical prerequisites.

These must be classified individually as:

- **FIXTURE DEBT** — old test directly creates/publishes a legacy menu without canonical Builder/link prerequisites, or
- **REAL PRODUCT PATH** — an actual reachable production writer still bypasses the canonical import/link seam.

Do **not** weaken fail-closed publication just to make old tests pass.

### D. Projection comparison differences

Two shadow/projection tests now disagree, likely around normalization/equivalence between canonical `dinner/main` and legacy `Kvall/kvall`.

Comparison must still detect real missing rows while treating correct semantic equivalents as matches.

### E. Old `Middag` expectations

Some tests still expect `Middag` while Kommun product terminology is now intended to be `Kvallsmat`.

Do not global replace. Inspect individual UI/report heading contracts and update only legitimate obsolete expectations. Offshore terminology must not be affected.

---

## 14. Current active ticket: KOMMUN-MENU-E2E-6D

Copilot is executing this ticket at handoff time.

Title:

**KOMMUN-MENU-E2E-6D — STABILIZE KITCHEN MENU READ CHAIN + CLOSE REGRESSIONS**

This is a correction/regression ticket, not new scope.

Priority order:

1. Reproduce an actual failing kitchen Weekview test with full traceback (`-vv --tb=long`).
2. Identify exact exception/file/line causing HTTP 500.
3. Fix the real root cause; do not suppress/catch just to produce HTTP 200.
4. Trace actual live readers for:
   - Kitchen Weekview
   - Kitchen Menyoversikt
   - Dashboard `Dagens meny`
   - shared menu modal/overview
5. Establish/reuse one normalized shared/core standard evening contract.
6. Standard evening canonical slot is `meal=dinner`, `variant=main`; legacy equivalent may be `Kvall/kvall`.
7. Make all kitchen consumers receive the same normalized evening truth.
8. Keep Portal independent; no Portal service dependency from core kitchen code.
9. Classify each `canonical_publication_missing` failure as fixture debt or real product path.
10. Preserve fail-closed canonical publication.
11. Fix projection comparison semantics without disabling comparison.
12. Update only legitimate obsolete Kommun `Middag` test expectations to `Kvallsmat`.
13. Run the exact 17 formerly failing tests first.
14. Then run the focused canonical/kitchen/portal/offshore bundle.
15. Do not run full suite until the exact 17 + focused bundle are green.

Explicitly out of scope during 6D:

- canonical Alt1/Alt2 single-truth cutover
- yellow Weekview state redesign
- Planera 1.0 redesign
- Planera 2.0 implementation
- Specialkost portal redesign
- resident-count portal redesign
- Synkad/Ej synkad indicator
- Portal layout redesign
- unrelated cleanup/refactor
- DB schema changes

No commit/push during 6D.

The new session should read the **final Copilot 6D report supplied by the user** and use it as the latest execution state.

---

## 15. Required acceptance after 6D

Do not commit immediately from a Copilot green report.

First perform real browser verification on `KommunTestA / 2026-W35`:

```text
1. Kitchen Weekview opens without 500.
2. Monday evening is Tomatsoppa med ostsmorgas.
3. Kitchen Menyoversikt shows evening meal for all seven days, not '-'.
4. Sunday dashboard today-menu shows Kottfarspaj med sallad as Kvallsmat.
5. Department Portal still shows menu.
6. Department Portal saved Alt choices/progress remain intact.
7. unpublish removes portal menu.
8. republish restores portal menu without re-import.
```

Then run full pytest.

Only if browser acceptance + full suite are green:

- inspect final diff
- `git diff --check`
- inspect `git status --short`
- commit the coherent canonical menu/publication/portal E2E block

---

## 16. Complete Kommun menu-consumer map — not fully done yet

We have mapped critical paths, but **not yet produced one exhaustive registry of every production consumer of published menu data**.

This matters because the Kvallsmat defect demonstrated that different kitchen screens can still use different read paths/normalization.

After 6D and commit, perform a short **READ-ONLY** ticket:

`KOMMUN-MENU-READ-MAP`

For every menu consumer, record:

```text
route/function
-> view/service/viewmodel
-> shared reader called
-> final canonical/legacy data source
-> meal/variant keys expected
-> whether local normalization/fallback exists
```

At minimum map:

- admin menu import/editor/publish UI
- kitchen Weekview
- kitchen Menyoversikt
- dashboard / today menu
- menu modal/overview
- planning screens
- reports/print surfaces that show menu text
- Planera 1.0
- Department Portal
- any compatibility APIs still serving menu text

Goal:

> all live menu-text consumers ultimately receive published menu truth through a deliberate shared normalization contract; no UI should independently reinterpret `dinner_main` or similar canonical keys.

This audit is inventory only. Do not turn every discovered legacy path into a refactor unless it violates current MVP correctness.

---

## 17. Canonical publication service notes

Canonical publication service:

`core/commun_builder_publication.py`

Known behavior:

- publish/sync uses linked Builder menu/projection
- missing link -> no publication
- projection is verified before publication
- publication snapshot captures pinned Builder identity/version and projection rows
- `get_publication_for_week(...)` is canonical read truth
- unpublish removes publication pin
- republish should pin latest linked Builder version if canonical prerequisites exist

Core invariant:

> No publication pin means the menu is not canonically published.

Do not reintroduce legacy published-state fallback in Portal or consumers that are supposed to read canonical publication.

---

## 18. Known Portal polish/backlog — not current blockers

These are known but deliberately deferred:

### False sync indicator

Portal displays `Synkad`, then may show `Ej synkad - ladda om` because JS compares different ETag domains (component choice ETag vs aggregate portal ETag).

Likely future action: remove or correctly scope the visible technical indicator while preserving concurrency protection under the hood.

Do not let this derail current menu/choice/Planera MVP sequence.

### Specialkost presentation

Current per-day Portal specialkost derives from actual Weekview day/meal facts, not simply department-linked diet configuration.

Product preference is likely to show department facts/counts in the information area rather than repeat Specialkost every menu day.

Future audit must find the existing canonical Kommun source for diet type/count; do not invent a new table.

### Resident count

Likewise, department resident/default count can later be shown in the Portal info/facts area. This is polish/information presentation, not current 6D scope.

---

## 19. Ground Truth / architecture docs

Important Ground Truth docs already in repository:

- `docs/ground_truth/README.md`
- `docs/ground_truth/YUPLAN_1_0_FINISHLINE.md`
- `docs/ground_truth/PLATFORM_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/BUILDER_MENU_LOCK.md`
- `docs/ground_truth/PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/PORTALS_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/OFFSHORE_1_0_MVP_LOCK.md`
- `docs/ground_truth/DECISION_LOG.md`

Ground Truth wins if an old implementation path or historical note conflicts with current architecture locks.

---

## 20. P2B / old portal cleanup — later

Old and canonical portal generations currently coexist.

P2B has not started.

Only after current canonical E2E acceptance should P2B:

- compare any unique behavior still present in the old portal
- redirect/decommission old routes after parity
- never create a third portal generation

---

## 21. Planera direction after Portal/menu truth is stable

Planera 2.0 remains the next major Kommun implementation after menu/menu-choice truth is stable.

Core architecture:

```text
Components
-> Dishes / Compositions
-> Menus
-> Published Menu
-> Kommun business context
-> Planera production engine
```

Normalkost remains baseline/single source of truth for normal production; specialkost is deviation.

Planera 2.0 should consume canonical published menu/component references through adapters, not create its own menu truth.

Do not start Planera 2.0 while the current kitchen menu read chain is still red.

---

## 22. MVP finishline from this checkpoint

Current practical sequence:

1. Finish 6D.
2. Manual browser verification.
3. Full suite.
4. Commit current canonical menu/publication/Department Portal E2E block.
5. READ-ONLY `KOMMUN-MENU-READ-MAP`.
6. Canonical department Alt1/Alt2 single-truth cutover:
   - Department Portal writer
   - Admin writer/change capability
   - kitchen Weekview yellow state reader
   - Dashboard/overview readers
   - relevant reports
   - Planera 1.0 consumer
7. Implement Planera 2.0 Kommun contracts/engine integration.
8. Bounded small Kommun polish only where needed.
9. Full manual E2E + full suite + pilot checklist.
10. Mark Kommun 1.0 **Ready for Pilot / MVP complete**.
11. Move primary product focus to Offshore 1.0.

---

## 23. What the new ChatGPT session should do first

The user will provide the latest Copilot 6D final report when opening the new chat.

New session should:

1. Read this handoff.
2. Read the user's pasted 6D final report.
3. Treat the report as newer than the pre-6D state documented here.
4. Review it strictly against the 6D invariants.
5. Do not open a new feature ticket until real Weekview/Menyoversikt/dashboard acceptance is green.
6. If 6D is code/test green, instruct the user through the small manual browser gate.
7. If manual gate is green, run full suite.
8. Only then prepare commit instructions.

Project-lead posture should remain conservative and linear.

---

## 24. Critical invariants to carry into every next ticket

1. One business fact, one canonical truth.
2. Builder owns canonical menu knowledge.
3. Published menu is immutable publication truth.
4. Portal is a consumer, never a source for kitchen core.
5. `department_menu_choices` is intended to become canonical explicit department meal-choice truth.
6. No explicit choice != Alt1.
7. Admin retains ability to change department choice by writing the same canonical truth.
8. Existing yellow Alt2 kitchen UX must survive the later cutover.
9. Planera 1.0 currently depends on Alt2-derived operational information and must be included in that cutover.
10. Canonical publication stays fail-closed.
11. Kommun presentation term is `Kvallsmat`; Builder may remain `dinner/main/dinner_main`.
12. Do not globally alter Offshore terminology/behavior.
13. No broad refactor merely because legacy code exists.
14. No commit while known real browser paths are red.

---

## 25. Handoff status marker

**Checkpoint status at file creation:**

`KOMMUN-MENU-E2E-6D IN PROGRESS`

The latest known pre-6D full suite is:

`17 failed, 1788 passed, 15 skipped, 3 warnings`

The latest known pre-6D real browser state is:

- Department Portal canonical menu + choices: GREEN
- publication/unpublication/republish: GREEN
- Kitchen Weekview: RED / HTTP 500
- Kitchen Menyoversikt evening meal: RED / missing

**Do not infer that these RED items remain after the user's next Copilot report. Verify the report and then perform the manual gate.**
