# Kommun 1.1 Handoff — 2026-09-28

## Purpose

This handoff is for continuing Yuplan Unified in a fresh ChatGPT/Copilot thread without reopening already accepted architecture or repeating completed gates.

Active development branch:

`feat/planera-app-shell-2026-03-03`

Latest accepted local product checkpoint:

`4dc54f3f9e7abddea9121d2f55a16be71596aff6`

`feat(kommun): bridge cohort completions into weekly reports`

Working rule:
- one small gate at a time;
- browser/live UX outranks DOM-only or test-only claims;
- reuse working Kommun 1.0 surfaces before rewriting;
- do not broaden MVP scope.

## Accepted chain

The following chain is accepted and should not be reopened without a proven regression:

Registered need
-> variable quantity
-> published menu + department menu choice
-> Product2 Page1
-> Product2 Page2 review
-> Planera 2.0
-> Page3 production underlay
-> Page3 completion
-> Kitchen Weekview
-> reload/persistence
-> Admin Weekview
-> Rapport / Statistik

Accepted completion checkpoint:

`aadfe9c4aecb64f8c14bd239193f687da0b4b2b7`

Accepted report bridge checkpoint:

`4dc54f3f9e7abddea9121d2f55a16be71596aff6`

Fresh E2E report proof:
- Avd11 Lunch: Normal 69 · Special 1.
- Avd13 Lunch: Normal 55 · Special 1.
- Avd16 Lunch: Normal 66 · Special 4.

## Current local uncommitted P0

Fresh pilot smoke found HTTP 500 on the admin department/Specialkost edit page because the template referenced missing endpoint:

`ui.admin_department_save_variation`

Latest Copilot implementation:
- restored a narrow compatibility POST endpoint in `core/ui_blueprint.py`;
- endpoint persists the existing **Varierat boendeantal** modal through `ResidentsScheduleRepo`;
- no DepartmentRequirementGroup / registered-need semantics changed;
- added focused coverage in `tests/ui/test_admin_departments_edit_specialkost.py`;
- focused test slice is green.

This is **not accepted/checkpointed yet**.

### Next single gate

Do not start menu/portal/UI work yet.

First:
1. restart current E2E runtime with the current code;
2. open the exact admin department edit page that previously returned 500;
3. verify HTTP 200;
4. verify existing registered needs render;
5. use **Varierat boendeantal**;
6. save one week/forever day-meal value;
7. reload and prove persistence;
8. inspect `git diff --check`, status and stat;
9. if clean, run focused regression and checkpoint the P0.

No redesign in this gate.

## Remaining Kommun 1.1 finish order

After the P0 checkpoint:

### 1. Menyimport -> Builder census

Read-only first.

Key question:

> When a municipal menu week is imported today, does it become the same Builder/Published Menu truth that Product2 consumes, or does a parallel legacy menu model still remain?

Desired architecture:

Menyimport
-> normalized menu content
-> Builder Menu
-> Published Menu
-> Avdelningsportal / Weekview / menu choice / Product2 / Planera 2.0

Rules:
- Menyimport is ingestion, not a second canonical menu system.
- Do not rebuild the working importer until the actual ownership seam is mapped.
- Product2 consumption of Published Menu is already accepted.

Also map current Kommun meal/menu semantics:
- lunch;
- zero/one/many lunch alternatives;
- dinner/kvällsmat;
- dessert.

These are Kommun adapter/application semantics, not universal Planera Core constraints.

### 2. Avdelningsportal census

The portal is not considered fully closed for pilot yet.

Existing foundation appears to include:
- department-scoped week view;
- menu display;
- resident/Specialkost read-only context;
- Alt1/Alt2 choice interaction;
- ETag-aware menu-choice mutation.

Census must verify:
- canonical current 1.1 route/template;
- Published Menu -> portal;
- portal menu choice -> same truth used by Kitchen/Product2;
- registered-needs/cohort read-only presentation;
- no conflicting legacy/duplicate portal path;
- role/site isolation;
- tablet usability.

Portal must never own resident or Specialkost writes.

### 3. Kommun UI/UX finish

This is planned and should happen before final pilot freeze.

Primary focus: department setup.

Target:
- compact **Registrerade behov** presentation;
- primary + modifiers readable without technical terms;
- default quantity immediately visible;
- `Varierat antal` collapsed/expandable instead of full 7 x 2 matrix always open;
- clear edit and, if operationally required, delete/retire action;
- remove/subordinate visible transition duplication between old Specialkost defaults and new Registrerade behov;
- align with current Yuplan Light/Dark visual system.

Also review:
- admin navigation / menu surfaces;
- Avdelningsportal presentation;
- Serveringstillägg/production-list transition wording;
- empty/error/status states.

Do **not** redesign working Kitchen/Admin Weekview or Rapport / Statistik without a proven usability problem.

### 4. Tablet / iPad finish

Manual responsive checks for:
- department setup;
- Product2 Page3;
- Kitchen Weekview;
- Rapport / Statistik;
- Avdelningsportal.

Only operationally blocking overflow/interactions are P0/P1. Minor spacing can remain polish.

### 5. Meal-path verification

Current Product2 completion E2E is proven for lunch.

Before pilot freeze:
- verify dinner/kvällsmat through current Product2 path;
- verify how Kommun dessert is mapped from Published Menu into production context;
- confirm no hard-coded Kommun meal assumptions have leaked into Planera Core.

Do not solve bakery/hotel/offshore menu structures in this Kommun finish phase.

### 6. Final fresh pilot smoke

Fresh E2E reset with actual Admin/Kitchen/Portal roles.

Verify:
- admin department setup;
- registered needs + variable counts;
- menu/published truth;
- portal menu choice;
- Product2 planning;
- Page3 completion;
- Kitchen/Admin Weekview;
- report;
- tablet-critical flows;
- no HTTP 500 or conflicting transition UI.

Only after this pass:

**Kommun 1.1 = PILOT READY**

## Servering / Packning decision

Do not automatically build a new packing module before first pilot.

Current stance:
- preserve existing Serveringstillägg;
- preserve printable production-list output;
- evaluate current output during finish smoke;
- dedicated structured packing projection is post-pilot unless a real operator problem proves it must move into pilot scope.

Long term, Specialkost production and Serveringsanpassning remain separate domains and may be combined only in a downstream pack projection.

## Planera 2.0 architecture guard

Planera Core is generic.

Do not hard-code:
- Kommun;
- department;
- Alt1/Alt2;
- lunch/dinner/dessert;
- Glutenfri/Timbal;
into generic Core rules merely because Kommun is the first completed vertical.

The current work is **Kommun 1.1 only**.

Other future menu structures may have:
- four lunch options and no dinner;
- breakfast/fika/banquet;
- bakery production with no meal concept;
- freeform production batches.

Those future verticals should enter through adapters/context, not by changing the Kommun MVP finish scope now.

## Ground-truth docs

Read first in a new thread:
- `docs/ground_truth/KOMMUN_1_0_MVP_LOCK.md`
- `docs/ground_truth/YUPLAN_1_0_FINISHLINE.md`
- `docs/ground_truth/PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/PORTALS_ARCHITECTURE_LOCK.md`
- `docs/planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md`

## Documentation branch note

The refreshed docs live on:

`docs/ground-truth-refresh-2026-09-28`

New documentation commits created after the local report checkpoint should be cherry-picked only after the current uncommitted P0 is checkpointed and the working tree is clean.

Do not overwrite local uncommitted product work with the docs branch.
