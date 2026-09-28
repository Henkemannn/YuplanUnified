Status: LOCKED
Last reviewed: 2026-09-28

# Kommun MVP Lock — Product2 / Kommun 1.1

## Release naming

- **Kommun 1.0** = existing legacy/pilot baseline and parity reference.
- **Kommun 1.1** = current Product2 + Planera 2.0 implementation being finished for the next pilot.
- **Yuplan 1.0** = wider platform MVP that includes a pilot-ready Kommun track plus Offshore 1.0.

This file keeps its historical path for continuity, but its active status describes **Kommun 1.1**.

## Current program status

Kommun 1.1 has now passed the core operational chain from registered need to reporting.

Accepted local checkpoints:
- `aadfe9c4aecb64f8c14bd239193f687da0b4b2b7` — Page3 -> Weekview completion flow.
- `4dc54f3f9e7abddea9121d2f55a16be71596aff6` — cohort completion/quantity bridge into existing weekly reports.

Fresh E2E proof has verified:
- Product2 Page2 reviewed state.
- Page3 exact Specialkost production targets.
- Page3 completion action.
- persisted cohort completion.
- Kitchen Weekview readback.
- Admin Weekview readback.
- weekly report readback with cohort quantities.

Verified report values for week 37 / 2026 after completion:
- Avdelning 11 Lunch: Normal 69 · Special 1.
- Avdelning 13 Lunch: Normal 55 · Special 1.
- Avdelning 16 Lunch: Normal 66 · Special 4.

The core chain is therefore established:

Admin registered needs
-> variable quantity
-> published menu + department menu choice
-> Product2 Page1/Page2/Page3
-> Planera 2.0 production truth
-> Kitchen Weekview completion
-> Admin Weekview
-> Rapport / Statistik

## Current active P0 gate

The fresh pilot smoke found one real admin blocker:

`ui.admin_department_save_variation`

The department edit template still referenced the old **Varierat boendeantal** form action, but the endpoint no longer existed, causing the admin Specialkost/department edit page to return HTTP 500.

Current local uncommitted fix:
- restore a narrow compatibility POST endpoint for the existing variation modal;
- persist through `ResidentsScheduleRepo`;
- do not change DepartmentRequirementGroup or registered-need semantics;
- focused `tests/ui/test_admin_departments_edit_specialkost.py` is green.

This fix is **not yet an accepted checkpoint** until:
1. live admin page returns 200;
2. Varierat boendeantal can save and reload;
3. the change is checkpointed with a clean tree.

Do not start the broader UI/UX finish before this P0 is closed.

## Canonical architecture

Builder remains canonical food/menu knowledge:

Components
-> Dishes / Compositions
-> Menus
-> Published Menu

Kommun owns business/operational context:
- departments/destinations;
- resident/baseline quantities;
- registered Specialkost needs;
- primary + modifiers;
- variable quantities;
- department menu choice;
- serving/packing preferences.

Planera 2.0 owns production calculation.

Planera Core must remain generic. Kommun-specific labels such as:
- department;
- Alt1 / Alt2;
- lunch / dinner;
- gluten;
- timbal;
- salad;
must stay in adapters/application layers unless a future cross-domain rule genuinely requires them.

The current Kommun implementation may use lunch/dinner/dessert semantics, but those are **Kommun adapter/UI semantics**, not universal Planera Core constraints.

## Menu / Builder status

Established:
- Builder/publication is the canonical menu direction.
- Published menu consumption in Product2/Planera is working.
- department Alt1/Alt2 menu-choice truth is working.
- missing menu choice must not silently fall back.

Still to verify before Kommun 1.1 pilot freeze:
- whether the existing **Menyimport** writes into the same Builder/published-menu truth or still maintains a parallel legacy menu path;
- whether imported CSV/DOCX weeks become editable/publishable in Builder without creating two competing menu truths;
- how Kommun maps lunch alternatives, dessert and dinner through the adapter without leaking those assumptions into Planera Core.

Desired end state:

Menyimport
-> normalized/imported menu content
-> Builder menu
-> Published Menu
-> Avdelningsportal / menu choice / Product2 / Planera 2.0

Menyimport must be an ingestion path, not a second canonical menu system.

## Avdelningsportal status

Avdelningsportalen is **not yet considered fully closed for pilot**.

Existing foundations already include:
- department-scoped weekly view;
- published menu display;
- resident/specialkost read-only context;
- Alt1/Alt2 menu-choice interaction;
- ETag-aware menu-choice mutation;
- portal tests and legacy parity documentation.

Before pilot freeze, run a focused portal census to verify:
- the current canonical 1.1 route/template;
- published Builder menu -> portal;
- portal menu choice -> same department-menu-choice truth used by kitchen/Product2;
- registered-needs/cohort information shown correctly and read-only;
- no duplicate/legacy portal path creates conflicting behavior;
- tablet usability and role isolation.

The portal must not own resident or Specialkost writes. Its mutable responsibility is department menu choice.

## Registered needs / Specialkost

Durable model:

**Specialkosttyp**
= atomic catalog item such as Glutenfri, Timbal, Laktosfri.

**Registrerat behov**
= one primary requirement + 0..N additional requirements/modifiers + quantity.

**Varierat antal**
= weekday/meal quantity overrides keyed to the registered need/cohort.

Rules:
- one recipient/cohort is counted once;
- modifiers do not create duplicate portions;
- unresolved legacy multi-requirement groups must not be guessed from name/order;
- exact requirement-member set remains available to Planera 2.0.

Remaining UI/UX finish:
- compact registered-need cards/rows;
- keep default quantity immediately visible;
- collapse the full 7 x 2 varied-quantity matrix behind `Varierat antal`;
- provide a clear edit and, if required for pilot operations, delete/retire path;
- remove or visually subordinate transition UI so old Specialkost defaults and new Registrerade behov do not look like competing truths.

## Product2 / Planera status

Complete and accepted:
- Page1 day overview foundation.
- Page2 human review.
- review persistence and staleness.
- review-aware Kommun -> Planera 2.0 adaptation.
- primary/modifier semantics.
- variable cohort quantities.
- meal orchestration.
- Page3 authoritative production projection.
- Normalkost and Specialkost quantities.
- destination breakdown.
- exact completion-target identity.
- atomic multi-department completion.
- optimistic concurrency / ETag validation.
- completion persistence and reload.

Current verified Product2 E2E scenario is lunch. Dinner support exists in the Kommun stack but should receive a current-branch verification during the finish pass. Dessert/menu-section semantics should be checked during the Menu/Builder census rather than generalized prematurely.

## Weekview status

Existing working surfaces are reused:
- Admin — Veckovy: read-only.
- Kök — Veckovy: operational/interactive.

Accepted:
- cohort rows;
- variable quantities;
- completion mark/unmark;
- persistence/reload;
- optimistic concurrency;
- Alt2 truth independent from completion truth;
- no third Weekview.

## Reporting status

The existing report page remains the product surface.

Accepted bridge:
- residents totals unchanged;
- cohort projection supplies completed Specialkost quantity where registered groups exist;
- legacy DietDefaults/marks path remains fallback only for legacy-only departments;
- cohort and legacy are never summed together for the same department;
- normal count = max(residents - completed special quantity, 0).

No new report UI or report engine was introduced.

## Servering / Packning status

Existing `Serveringstillägg` and printable production-list output remain valid transition behavior.

Current decision for first pilot:
- do **not** build a new dedicated packing module unless the finish smoke proves the existing output is operationally insufficient;
- production, destination breakdown and Serveringstillägg may remain in the existing printable surface for the first pilot;
- a dedicated structured packing projection is a post-pilot improvement unless promoted by a proven pilot blocker.

Long-term architecture remains:
- Specialkost production truth and Serveringsanpassning are separate domains;
- a combined pack list may project both downstream;
- packing must not become a second production-calculation engine.

## Remaining to Kommun 1.1 MVP / pilot

### P0 — must close before further finish work

1. **Admin Varierat boendeantal 500**
   - live-verify the restored compatibility endpoint;
   - save/reload week or forever resident schedule;
   - checkpoint the fix.

### P1 — finish before pilot freeze

2. **Menyimport -> Builder census**
   - determine whether one or two menu truths still exist;
   - lock the ingestion path into Builder/published menu;
   - no broad Builder redesign.

3. **Avdelningsportal census**
   - verify current route/template/data ownership;
   - verify published menu and menu-choice round trip;
   - verify read-only Specialkost/department facts;
   - identify only real pilot gaps.

4. **Kommun UI/UX finish**
   - clean department setup;
   - compact Registrerade behov / Varierat antal;
   - reduce transition duplication;
   - clarify admin navigation/menu surfaces;
   - polish portal where needed;
   - preserve working Weekview and Report layouts.

5. **Tablet/iPad finish pass**
   - department setup;
   - Product2 Page3;
   - Kitchen Weekview;
   - Rapport;
   - Avdelningsportal.

6. **Current-branch meal semantics verification**
   - lunch already proven;
   - verify dinner/kvällsmat in Product2;
   - verify dessert mapping in Kommun menu adapter;
   - confirm no Kommun-specific meal assumptions have leaked into Planera Core.

7. **Final fresh pilot smoke**
   - real Admin + Kitchen roles;
   - fresh E2E reset;
   - admin setup -> menu -> Planera -> completion -> Weekview -> report;
   - portal/menu-choice readback;
   - no HTTP 500 / stale transition blockers.

### P2 — post-pilot unless promoted by real pilot evidence

- dedicated structured packing projection;
- advanced Serveringsanpassning rule editor;
- full dead-code cleanup;
- broad legacy route removal;
- advanced analytics/billing integration;
- Home / Hotel / Banquet/Event work.

## Pilot-ready definition

Kommun 1.1 is pilot-ready when:
- current P0 admin blocker is closed;
- Menyimport/Builder ownership is unambiguous;
- Avdelningsportal has passed its focused census and any true blocker is closed;
- department/admin UI has received the planned compact finish pass;
- critical surfaces work on iPad/tablet;
- fresh end-to-end operator smoke passes.

Do not reopen core Planera architecture, invent a third Weekview, redesign the existing report, or generalize all future business types during this finish phase.

## Related ground truth

- `docs/ground_truth/YUPLAN_1_0_FINISHLINE.md`
- `docs/ground_truth/PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/PORTALS_ARCHITECTURE_LOCK.md`
- `docs/planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md`
