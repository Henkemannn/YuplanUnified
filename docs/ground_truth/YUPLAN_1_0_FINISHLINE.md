Status: LOCKED
Last reviewed: 2026-09-28

# Yuplan 1.0 Finishline

## Current phase

Release naming:
- **Kommun 1.0** = legacy/pilot parity baseline.
- **Kommun 1.1** = Product2 + Planera 2.0 track for the next municipal pilot.
- **Offshore 1.0** = first offshore MVP track.
- **Yuplan 1.0** = platform MVP containing pilot-ready Kommun 1.1 plus Offshore 1.0.

Active phase:

**Kommun 1.1 — finish the remaining pilot shell/integration debt, then freeze and return to Offshore.**

The main production chain is no longer the active risk. Product2 -> Planera 2.0 -> Weekview completion -> reporting has been proven on a fresh E2E scenario.

## Accepted local checkpoints

- `aadfe9c4aecb64f8c14bd239193f687da0b4b2b7`
  - `feat(planera): complete page3 to weekview completion flow`
- `4dc54f3f9e7abddea9121d2f55a16be71596aff6`
  - `feat(kommun): bridge cohort completions into weekly reports`

Current local P0 work is uncommitted:
- restore the missing `ui.admin_department_save_variation` compatibility endpoint for the existing Varierat boendeantal modal;
- persist via `ResidentsScheduleRepo`;
- focused admin department test is green;
- live verification and checkpoint still remain.

## Established Kommun 1.1 chain

Published menu
-> department menu choice
-> registered needs + variable quantity
-> Product2 Page1
-> Product2 Page2 human review
-> Planera 2.0
-> Page3 production underlay
-> cohort completion
-> Kitchen Weekview
-> Admin Weekview
-> existing Rapport / Statistik

Fresh E2E proof has verified the completion and reporting path.

## What remains before Kommun 1.1 pilot freeze

1. Close/checkpoint the admin Varierat boendeantal P0.
2. Census Menyimport -> Builder and eliminate ambiguity about canonical menu ownership.
3. Census Avdelningsportal and close only real pilot gaps.
4. Consolidated Kommun UI/UX finish, led by department setup / Registrerade behov / Varierat antal.
5. Tablet/iPad visual-operational pass.
6. Verify current Product2 dinner/kvällsmat path and Kommun dessert mapping without generalizing Planera Core.
7. Final fresh Admin + Kitchen + Portal operator smoke.

Current first-pilot stance on Servering / Packning:
- preserve existing Serveringstillägg and printable production-list behavior;
- do not create a new packing module unless the finish smoke proves the current output insufficient;
- dedicated structured packing projection may follow after the pilot.

## Menu / Builder boundary

Builder owns canonical food/menu knowledge:

Components -> Dishes/Compositions -> Menus -> Published Menu.

Product2 consumption of Published Menu is established.

Open finish question:
- does existing Menyimport feed that same Builder/published-menu truth, or does a parallel legacy menu path remain?

Desired end state:

Menyimport -> Builder Menu -> Published Menu -> Portal / Weekview / Product2 / Planera.

No second canonical menu system.

## Planera 2.0 boundary

Planera Core remains generic.

Kommun can map:
- lunch;
- dinner/kvällsmat;
- lunch alternatives;
- dessert;
through its adapter/application layer.

Do not turn those Kommun concepts into universal Planera Core constraints.

Future business types such as Offshore, hotel/event, bakery or freeform production may expose different menu/service structures. That future generalization is not a reason to expand the current Kommun MVP scope.

## Avdelningsportal boundary

The portal must:
- show the department's published menu and relevant read-only facts;
- allow department menu choice;
- write only menu-choice state;
- not own resident/Specialkost truth.

A focused current-branch portal census remains before pilot freeze.

## Freeze rules

Do not:
- reopen broad Builder work;
- redesign the working Weekview;
- redesign the working Report page;
- build a third Weekview;
- introduce a second menu truth;
- generalize every future vertical now;
- turn E2E/test infrastructure into its own project.

## After Kommun 1.1 pilot-ready

1. Freeze Kommun except pilot-blocking defects.
2. Run a fresh Offshore 1.0 census.
3. Resume Offshore implementation only from that census.
4. Close Yuplan 1.0 release gate across included Kommun + Offshore surfaces.

## Out of Yuplan 1.0 MVP unless promoted by proven blocker

- Yuplan Home;
- Hotel/Bankett/Event;
- advanced analytics;
- external billing integrations;
- full arbitrary serving-rule editor;
- full dead-code cleanup;
- broad recipe-engine expansion.
