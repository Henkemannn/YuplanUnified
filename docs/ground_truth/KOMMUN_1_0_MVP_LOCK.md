Status: LOCKED
Last reviewed: 2026-09-23

# Kommun 1.0 MVP Lock

## Goal

Yuplan Kommun 1.0 must provide one coherent operational flow from published menu to production and packing for a municipal kitchen.

The MVP must preserve the useful current Kommun behavior while moving production truth to the canonical Builder -> Business Context -> Planera 2.0 architecture.

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
-> daily packing / destination output

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
- existing Serveringstillägg during transition

Missing menu choice must not silently fall back to another option.

## Human Review

Page2 answers:

> Which recipient cohorts cannot eat the current published dish as it is?

Review state is separate from quantity truth.

- UNREVIEWED is not equivalent to no adaptations.
- stale review is not current production truth.
- current reviewed NO means no adaptation for that cohort.
- current reviewed YES becomes production deviation input.
- current quantities always come from current business context.

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

Kommun-specific interpretation belongs in adapters / application layers.

## Meal Orchestration

Meal-level orchestration must:

- derive the current published options
- derive current destination assignment
- expose unassigned destinations separately
- require current review only for options with demand
- skip zero-demand options without inventing production
- run reviewed demanded options through acceptance and Planera Core
- preserve multiple blockers simultaneously
- not create fake meal-wide totals across unlike dishes

## Page3 Production Underlay

Page3 is the first user-facing projection of Planera 2.0 production truth.

Minimum MVP direction:
- published option / dish
- assigned destinations
- standard production quantity
- adapted production requirements
- destination breakdown
- readiness / blocker information
- traceability to the current service and publication

The UI may evolve after live testing, but it must consume orchestration / Planera output instead of recalculating production independently.

## Parallel Run / Parity

Planera 1 and Planera 2.0 must run in parallel before cutover.

Parity should compare:
- department inputs
- menu choices
- baseline quantities
- requirement quantities
- normal / standard production
- adapted production
- destination breakdown
- Serveringstillägg where currently supported

A difference must be classified before cutover as:
- regression
- legacy-model limitation
- intentional new behavior

Planera 2.0 becomes Kommun production truth only after parity acceptance.

## Serveringstillägg and Standing Needs

The existing Serveringstillägg feature is retained as valid transition input.

Current fixed additions such as:
- Mos
- Sallad
- Sauce separately / other site-specific additions

must remain available through the transition and be represented in daily operational / packing output.

The long-term model must support more than fixed addon families.

It must allow structured:
- standing additions
- exclusions
- conditional component substitutions
- serving / handling instructions

The architecture must remain open to any user-defined component replacement, for example:
- boiled potato -> mashed potato
- pasta -> mashed potato
- spaghetti -> macaroni

Do not hardcode only current examples.

## Menu-Aware Rules

Structured standing rules should be resolved against canonical Builder component knowledge.

If a replacement is already the normal published component, Yuplan must not create duplicate production or duplicate packing.

Example:

Rule:
- potato or pasta -> mashed potato

Published dish already contains mashed potato:
- no extra mashed-potato requirement

This resolution belongs above Planera Core.

## Daily Packing

Daily destination-aware packing output is part of Kommun 1.0 operational finishline.

The kitchen must be able to determine:
- what is packed
- quantity
- meal / date
- department / destination
- standard vs adapted item where relevant
- standing addon / substitution / handling need where relevant

Packing is a projection of shared production / operational truth, not a separate calculation engine.

Existing fixed Serveringstillägg must be represented in this output.

## Specialkost Registration

A complete rewrite of the current department specialkost registration UI is not required before Planera 2.0 cutover.

For 1.0:
- preserve usable current registration surfaces
- translate to canonical requirement cohorts through explicit adapters / migration
- do not guess semantics from free text

Later UX modernization should favor:
- atomic requirement definitions
- explicit combined cohorts
- structured standing operational needs
- less proliferation of combined legacy labels

## Required Before Ready for Pilot

- normal authenticated Kommun flow works
- Product2 Page1 works from current published menu
- Product2 Page2 review works
- review persistence / staleness works
- meal orchestration is accepted
- Page3 production underlay works
- realistic multi-department E2E passes
- Planera 1 / 2 parity is reviewed
- daily packing output works
- existing fixed Serveringstillägg is preserved
- iPad / print / operational usability receives final acceptance

## Not Required to Block First Pilot

These may follow after the first pilot if the architecture already supports them:

- full arbitrary substitution-rule editor
- complete conversion of all free-text notes to structured rules
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
