Status: LOCKED
Last reviewed: 2026-09-24

# Kommun 1.0 MVP Lock

## Goal

Yuplan Kommun 1.0 must provide one coherent operational flow from published menu to production and packing for a municipal kitchen.

The MVP must preserve the useful current Kommun behavior while moving production truth to the canonical Builder -> Business Context -> Planera 2.0 architecture.

## Current Implementation Status

As of 2026-09-24:

- Product2 Page1 foundation is complete.
- Product2 Page2 review foundation is complete.
- option-review persistence and staleness are complete.
- review-aware Kommun -> Planera 2.0 adapter is complete.
- meal-level orchestration is complete.
- Page3 has an authoritative Planera 2.0-backed projection foundation.
- Page3 final information architecture and visual acceptance are active work.
- the current Page3 checkpoint is `77d73e637f055378b5e82a9385170b9e84346373`.
- that checkpoint is intentionally not visually accepted.
- explicit Specialkost primary/modifier persistence is not implemented yet.

Known READY E2E production truth remains:
- Vardagsgryta: total 79, normal 79, special 0.
- Ugnsbakad fisk: total 62, normal 54, special 8.

## Required End-to-End Flow

Builder
-> Published Menu
-> Department Portal / menu choice
-> current department baseline and requirements
-> Product2 Page1 day overview
-> Product2 Page2 human review
-> meal orchestration
-> Planera 2.0
-> Page3 production underlay
-> separate Servering / Packning projection

The flow must be usable by a normal site-bound kitchen user.

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

The final Kommun 1.0 Specialkost production presentation needs explicit hierarchy.

Locked target:

**one primary requirement + 0..N modifiers**

Example:

`Timbal + Glutenfri`

means:
- primary production group: Timbal
- modifier/additional requirement: Glutenfri
- the recipient/cohort is counted once under Timbal
- the same recipient must not also create a separate top-level Glutenfri production count

The hierarchy is user-authored and authoritative.

Yuplan must not automatically decide that one named requirement "wins" over another.

### Persistence direction

Current `department_requirement_group_requirements` membership is unordered and preserves the full exact combination but not role/order.

Smallest preferred durable 1.0 model:
- nullable `primary_requirement_id` on `department_requirement_groups`
- existing requirement membership remains the complete set
- service layer validates that primary is a member of the group
- all other members are modifiers

Planera 2.0 Core does not need to know which member is primary for current production arithmetic.

Core remains order-agnostic and consumes the full exact requirement combination.

Primary/modifier is registration, application and presentation semantics unless a future engine rule requires otherwise.

### Legacy migration

Do not infer primary from:
- display name
- requirement name
- sorted order
- array position
- hardcoded priority such as "Timbal always wins"

Safe rule:
- single-requirement group -> its sole requirement is unambiguous
- multi-requirement legacy group -> unresolved until explicitly assigned unless a trustworthy source already stores the hierarchy

## Specialkost Registration UX Direction

The target registration flow is:

1. create/select the primary specialkost requirement
2. inside that primary item, add 0..N additional requirements

Example:

`Timbal`
-> `+ Lägg till avvikelse`
-> `Glutenfri`

Result:

`[Timbal] + [Glutenfri]`

If the user instead creates Glutenfri as primary and adds Timbal as a modifier, that hierarchy is stored as entered. Yuplan does not silently reverse it.

This direction replaces the previous long-term idea that all combinations should remain visually flat.

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

## Current Page3 Visual Acceptance Debt

The current code checkpoint `77d73e637f055378b5e82a9385170b9e84346373` is a checkpoint, not acceptance.

Manual review still shows:
- old large date/hero treatment
- old `Klar` wording in runtime
- old `Tillbaka till granskning` presentation
- `Produktion / Per avdelning` controls visible where they should not be
- Overview can appear as raw text instead of the intended table
- Specialkost still presents exact combinations such as `Timbal + Laktosfri`
- dark mode contains overly dark/flat sections
- final Light/Dark polish remains

Do not mark Page3 complete based only on green focused tests.

## Product2 E2E Runtime

For manual Product2 visual review, use a deterministic single-process runtime until the local runtime is hardened.

Known-good pattern:
- one server process
- port 5000
- canonical `product2_e2e.db`
- canonical `product2_e2e_builder.db`
- `debug=False`
- `use_reloader=False`

A live POST to the real port-5000 `/auth/login` has been proven successful in that configuration.

The ordinary debug/reloader launch path must not be used as evidence of E2E correctness until the discrepancy is hardened away.

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

- normal authenticated Kommun flow works
- Product2 Page1 works from current published menu
- Product2 Page2 review works
- review persistence / staleness works
- meal orchestration remains accepted
- Page3 production underlay is visually and operationally accepted in Light + Dark
- explicit primary/modifier Specialkost semantics are persisted and correctly projected
- realistic multi-department E2E passes
- Planera 1 / 2 production parity is reviewed
- separate Servering / Packning output works
- existing fixed Serveringstillägg is preserved in that separate surface
- daily destination-aware packing output works
- iPad / print / operational usability receives final acceptance

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
