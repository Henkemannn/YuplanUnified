Status: LOCKED
Last reviewed: 2026-09-28

# Kommun MVP Lock — Product2 / Kommun 1.1


## Goal

Yuplan Kommun must provide one coherent operational flow from published menu to production, completion, reporting and packing for a municipal kitchen.

Release naming used by the active project:
- **Kommun 1.0** = existing legacy/pilot baseline that remains the parity reference.
- **Kommun 1.1** = the current Product2 + Planera 2.0 implementation being finished for the next pilot.

This file keeps its historical path for continuity, but its active implementation status now describes **Kommun 1.1**.

The MVP must preserve the useful working Kommun 1.0 behavior while moving production truth to the canonical Builder -> Business Context -> Planera 2.0 architecture. Reuse working Weekview, registration and admin surfaces before rewriting them.


## Current Implementation Status

As of 2026-09-28:

Complete / accepted foundations:
- Product2 Page1 foundation.
- Product2 Page2 human-review foundation.
- option-review persistence and staleness.
- explicit Specialkost primary semantics through `primary_requirement_id`.
- recurring/variable registered-need quantity persistence.
- review-aware Kommun -> Planera 2.0 adapter.
- meal-level orchestration.
- Page3 authoritative Planera 2.0-backed production projection.
- Page3 Specialkost primary/modifier presentation foundation.
- shared Admin/Kitchen Weekview cohort projection.
- Kitchen cohort completion writes with optimistic concurrency.
- exact Page3 completion-target contract.
- atomic multi-department cohort completion coordinator.
- Product2 completion API with exact per-department ETag validation.

Latest accepted local code checkpoint before the current uncommitted gate:

`2364ba475a7ed8d16087d7f60f9fadf25756c945`

`feat(planera): add product2 cohort completion api`

Current uncommitted gate:
- visible Page3 completion button/client flow;
- remove the incorrect legacy `ff.planera.enabled` guard from Product2 completion;
- finish one clean deterministic manual Page3 -> Weekview E2E proof.

Focused regression after the guard correction: **90 passed, 0 failed, 0 skipped**.

Manual runtime proof already established:
- Page3 completion can reach `Markerat i veckolistan ✓`;
- cohort rows persist as completed in Kitchen Weekview;
- Alt 2 yellow state is independent menu-choice truth and was not written by the completion path.

The remaining E2E issue is fixture hygiene: the generic Product2 seed starts Page2 UNREVIEWED and intentionally seeds Alt 2 menu choices for some departments, so a reused DB is not a canonical four-target completion scenario.

Final Page3 micro-polish is deliberately deferred until the functional/reporting/parity chain is closed.


## Required End-to-End Flow

Builder
-> Published Menu
-> Department Portal / menu choice
-> current department baseline and registered needs
-> Product2 Page1 day overview
-> Product2 Page2 human review
-> meal orchestration
-> Planera 2.0
-> Page3 production underlay
-> Kitchen Weekview completion
-> reporting/statistics projection
-> separate Servering / Packning projection

The flow must be usable by a normal site-bound kitchen/cook user.

Admin Weekview is read-only operational oversight. Kitchen Weekview owns manual produced/done interaction.

The existing working Weekview surfaces are reused:
- Admin — Veckovy: read-only;
- Kök — Veckovy: operational/interactive.

Do not create a third Weekview to support Product2.

## Canonical Inputs

Kommun 1.0 production input must come from current canonical sources:

- published Builder menu / publication snapshot
- department menu choices
- department baseline / resident quantities
- canonical atomic dietary / texture requirements
- disjoint DepartmentRequirementGroup cohorts
- current service overrides
- human option review against the current published dish

Existing Serveringstillägg remains valid transition input for the separate serving/packing track.

Missing menu choice must not silently fall back to another option.

## Specialkost vs Serveringsanpassning

This separation is locked.

### Specialkost

Recipient-level / recipient-cohort needs that may affect what must be produced.

Examples:
- one recipient never tomato
- gluten-free
- timbal
- vegetarian
- no fish

Specialkost belongs in the requirement/cohort flow:

requirements
-> Page2 human review
-> Planera 2.0
-> normal + adapted production

### Serveringsanpassning

Department/destination-level serving, packing or delivery preferences.

Examples:
- salad for 6
- the department never wants tomato in its salad
- sauce separately
- mashed potato instead of boiled potato
- macaroni instead of spaghetti

Serveringsanpassning must not be mixed into the default normal/specialkost production worklist.

It belongs in a separate Servering / Packning operational surface.

A similar phrase can therefore belong to different domains depending on scope:

- one recipient never tomato -> Specialkost
- whole department wants salad without tomato -> Serveringsanpassning

## Human Review

Page2 answers:

> Which recipient cohorts cannot eat the current published dish as it is?

Review state is separate from quantity truth.

- UNREVIEWED is not equivalent to no adaptations.
- stale review is not current production truth.
- current reviewed NO means no adaptation for that cohort.
- current reviewed YES becomes production deviation input.
- current quantities always come from current business context.

Serveringsanpassningar do not enter Page2 merely because they may later affect packing.


## Specialkost Primary / Modifier Semantics

Explicit hierarchy is now part of the durable Kommun model:

**one primary requirement + 0..N modifiers**

Example:

`Timbal + Glutenfri`

means:
- primary production group: Timbal
- modifier/additional requirement: Glutenfri
- the recipient/cohort is counted once
- the full exact requirement-member set remains available to Planera 2.0

Implemented persistence direction:
- `primary_requirement_id` exists on `department_requirement_groups`;
- primary must belong to the group member set;
- all remaining members are modifiers;
- single-requirement groups are unambiguous;
- unresolved legacy multi-requirement groups must not be guessed from names/order.

Planera 2.0 Core remains order-agnostic and consumes the full exact combination. Primary/modifier remains application/registration/presentation semantics unless a future production rule genuinely requires more.


## Specialkost Registration UX Direction

Current conceptual model:

**Specialkosttyper**
= atomic catalog/library such as Glutenfri, Timbal, Laktosfri.

**Registrerat behov**
= one primary requirement + 0..N additional requirements/modifiers + quantity.

**Varierat antal**
= the existing familiar weekday/meal quantity concept, now keyed to the registered need/cohort rather than an isolated atomic diet type.

The current data/function is accepted. Remaining work is presentation polish:
- compact each registered need;
- keep default quantity visible;
- collapse the full 7 x 2 varied-quantity matrix behind `Varierat antal`;
- avoid presenting the transition between old Specialkost configuration and new Registrerade behov as two competing truths.

Do not remove old transition data until parity/cutover proves it is safe.

## Planera 2.0

Planera 2.0 is the production calculation layer.

For each demanded menu option it must produce deterministic standard and adapted production quantities with destination traceability.

The Core remains generic and must not contain Kommun-specific concepts such as:
- department
- Alt1 / Alt2
- gluten
- timbal
- salad
- mash
- tomato
- spaghetti

Kommun-specific interpretation belongs in adapters / application layers.

Serveringsanpassningar are not automatically Planera deviations.

Primary/modifier hierarchy must not be hardcoded into Planera Core while the engine only needs the exact requirement combination.

## Meal Orchestration

Meal-level orchestration is complete for the current Product2 production path.

It:
- derives the current published options
- derives current destination assignment
- exposes unassigned destinations separately
- requires current review only for options with demand
- skips zero-demand options without inventing production
- runs reviewed demanded options through acceptance and Planera Core
- preserves multiple blockers simultaneously
- does not create fake meal-wide totals across unlike dishes

Serveringstillägg remains outside this production orchestration gate.

## Page3 Production Underlay

Page3 is the user-facing projection of Planera 2.0 production truth.

### Locked information architecture

One production context, three equal work tabs:

- Översikt
- Normalkost
- Specialkost

Exactly one main work area is active at a time.

No duplicate local navigation hierarchy should appear.

### Shared context/header

Target:
- global Yuplan topbar retained
- compact `Produktionsunderlag` title
- operational date context
- kitchen/site + meal
- quiet review action
- status wording `Underlag granskat` when orchestration/review basis is READY

The status must not imply that cooking/production itself is finished.

### Översikt

One compact authoritative table:
- Menyval
- Totalt
- Normalkost
- Specialkost
- total row

Do not duplicate the same truth in large summary cards.

### Normalkost

Destination x published-menu-choice matrix:
- destination first column
- one column per published option
- dish title and total in header
- zero as dash
- total row
- horizontal scroll for many options
- no unexplained row highlight

### Specialkost target

When explicit primary/modifier persistence exists:

`PRIMARY REQUIREMENT                   total`

`Avdelning 11 [neutral menu-choice pill] [modifier pill] quantity`

Menu-choice pill:
- context only
- neutral visual weight
- means the department's ordinary published menu choice
- does not claim that the specialkost recipient necessarily receives that exact dish

Modifier pill:
- visually distinct from neutral menu choice
- planned subtle purple token family
- inline on the same row
- multiple modifiers allowed

Grouping:
- `Avdelning | Menyval` is a presentation toggle only
- same recipients
- same totals
- no arithmetic changes
- no duplicate counting

### Current-safe rule

Until primary/modifier persistence exists, Page3 must keep truthful exact-combination semantics and must not fake a primary requirement from names or order.


## Product2 Completion and Weekview

Completion semantics are locked:

- `quantity` = planned production need.
- `completion/done` = produced/handled operational outcome.
- `Alt 2` = independent department menu-choice state.
- reporting later consumes completion + quantity truth.
- external billing is not part of Kommun 1.1.

Product2 completion identity is cohort identity, never a fake diet type.

Page3:
- derives exact completion targets server-side from `planning_slice.context["requirement_group_refs"]`;
- includes only current adaptation-required cohort refs;
- does not use visual combination aggregation as mutation identity.

Browser:
- receives only the affected department IDs plus page context;
- fetches current Weekview ETags per affected department;
- sends no cohort/group/diet identity in the completion POST.

API:
- rebuilds Page3 server-side;
- validates the exact affected-department ETag set;
- converts effective ETags to current base versions;
- calls the atomic multi-department coordinator.

Atomic coordinator:
- uses one session/transaction;
- bumps each affected department version once;
- writes completion rows only after all CAS checks succeed;
- rolls back all versions/completions on stale/error;
- never writes legacy `weekview_registrations`.

Weekview rendering keeps states independent:
- completion -> green completion indicator;
- Alt 2 -> yellow background;
- both may coexist only when both truths are independently present.

A live investigation proved the observed yellow state in the reusable E2E DB came from pre-existing `department_menu_choices` rows, not from Product2 completion writes.

## Current Page3 UX Status

The old 2026-09-24 visual-debt list is no longer the active blocker.

Current accepted direction:
- compact production context;
- tabs Översikt / Normalkost / Specialkost;
- Specialkost Produktionslista / Packlista where applicable;
- primary requirement as the main production grouping;
- destination + quantity as primary row context;
- modifiers as quiet secondary pills;
- completion action applies to the whole current date/meal production context.

Final Light/Dark, iPad, status/error and spacing polish is deferred to the consolidated Kommun UI finish after reporting/parity bridges are functional.

Do not reopen broad Page3 redesign during the remaining backend/E2E gates.


## Product2 E2E Runtime

Normal local development:
- `python run.py`
- ordinary local `dev.db`

Canonical Product2 E2E/manual review:
- `instance/product2_e2e.db`
- `instance/product2_e2e_builder.db`
- one process
- port 5000
- `debug=False`
- `use_reloader=False`

Verified E2E identities:
- Kitchen/cook account: `e2e.kitchen@yuplan.local`
- Admin account: `e2e.admin@yuplan.local`

The generic base E2E seed is not itself a canonical completion scenario:
- it intentionally starts Page2 UNREVIEWED;
- it intentionally seeds broad Alt1/Alt2 menu-choice data.

For destructive/manual completion acceptance, apply only a very small deterministic completion-scenario overlay/reset. This must not turn into a general E2E framework or multi-day seed refactor.

The Product2 completion manual gate is considered proven only from a clean before-state:
- exact expected completion targets;
- target cells not already completed;
- no misleading Alt 2 state on the target cells unless the scenario intentionally requires it.

## Parallel Run / Parity

Planera 1 and Planera 2.0 must run in parallel before cutover.

Production parity should compare:
- department inputs
- menu choices
- baseline quantities
- requirement quantities
- normal / standard production
- adapted production
- destination breakdown

Servering parity should be compared separately:
- existing Serveringstillägg counts
- department breakdown
- notes
- future structured serving rules

A difference must be classified before cutover as:
- regression
- legacy-model limitation
- intentional new behavior

Planera 2.0 becomes Kommun production truth only after parity acceptance.

## Serveringstillägg and Serveringsanpassning

The existing Serveringstillägg feature is retained as valid transition input.

Current fixed additions such as:
- Mos
- Sallad
- Sauce separately / other site-specific additions

must remain available through the transition, but in a separate serving/packing track.

The long-term model must support more than fixed addon families.

It must allow structured:
- standing additions
- department-level exclusions
- conditional component substitutions
- serving / handling instructions

The architecture must remain open to any user-defined component replacement, for example:
- boiled potato -> mashed potato
- pasta -> mashed potato
- spaghetti -> macaroni

Do not hardcode only current examples.

## Menu-Aware Servering Rules

Structured serving rules should be resolved against canonical Builder component knowledge.

If a replacement is already the normal published component, Yuplan must not create duplicate output.

Example:

Rule:
- potato or pasta -> mashed potato

Published dish already contains mashed potato:
- no extra mashed-potato serving requirement

This resolution belongs outside Planera Core.

## Daily Packing

Daily destination-aware packing output is part of Kommun 1.0 operational finishline.

The kitchen must be able to determine:
- what is packed
- quantity
- meal / date
- department / destination
- standard vs adapted production item where relevant
- serving addon / substitution / handling need where relevant

Packing is a projection over shared truths, not a separate calculation engine.

## Optional Combined Total Pack List

A later total pack view may deliberately combine the separate tracks for the final packing task.

Example:

Solrosen — Avdelning 1

- Normalkost: 8
- Timbal: 1
- Sallad: 6 — aldrig tomat
- Potatismos istället för kokt potatis: 1

This combined view may be generated:
- for one department
- for one delivery location / boende
- for all departments

It is an explicit downstream projection.

It must not collapse Specialkost and Serveringsanpassning into one data model or one default production worklist.


## Required Before Ready for Pilot

Already established:
- normal authenticated Product2 Kitchen and Admin access.
- Product2 Page1 from current published menu.
- Product2 Page2 review + persistence/staleness.
- explicit primary/modifier registered-need semantics.
- variable cohort quantities.
- meal orchestration.
- authoritative Page3 production projection.
- shared cohort Weekview read model.
- Kitchen cohort completion persistence.
- exact Page3 completion targets.
- atomic multi-department completion service.
- Product2 completion API / ETag concurrency bridge.

Remaining:
- close and checkpoint the visible Page3 completion client flow with one clean manual Page3 -> Kitchen Weekview -> reload -> Admin Weekview proof.
- reporting/statistics bridge over new cohort quantity + completion truth.
- one full Kommun E2E from Admin registered need through report.
- Kommun 1.0 vs Kommun 1.1 parity/cutover review.
- consolidated operational UI/UX finish including compact Varierat antal editing, empty/error/status states, iPad and Light/Dark consistency.
- separate Servering / Packning output.
- preserve existing fixed Serveringstillägg in that separate surface.
- daily destination-aware packing output.
- final pilot smoke/regression/deploy checks.

A difference versus Kommun 1.0 must be classified as:
- regression;
- old-model limitation;
- intentional new semantics.

Do not rewrite working Kommun 1.0 behavior merely to make the new track look different.

## Not Required to Block First Pilot

These may follow after the first pilot if the architecture already supports them:

- full arbitrary substitution-rule editor
- complete conversion of all free-text notes to structured rules
- polished combined total-pack UI
- recipient-level identity model
- advanced delivery-location hierarchy
- recipe scaling
- inventory / purchasing
- freezer / prep automation
- AI suggestions

## Detailed Reference

See:

- `docs/planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md`
- `docs/ground_truth/PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/YUPLAN_1_0_FINISHLINE.md`
