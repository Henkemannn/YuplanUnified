Status: LOCKED
Last reviewed: 2026-09-23

# Planera 2.0 Architecture Lock

## Purpose

Planera 2.0 is a generic production engine.

Core question:

> What needs to be produced?

The wider Planera application layer may project that production truth into downstream operational views, but those views must not become competing calculation engines.

## Preserved Principles

- context-neutral
- compute-first
- deterministic
- headless
- independently testable
- adapter-based
- no business-specific logic in templates or core
- small responsibility, strong structure

Builder is the Knowledge Source of Truth.

Planera consumes food knowledge; it does not duplicate it.

## Canonical Flow

Builder -> Components -> Dish -> Menu -> Published Menu
-> Business Context / Effective Menu
-> Demand
-> Compatibility / Requirements
-> Planning Slice / orchestration
-> Planera 2.0 Core
-> Production Requirement / PlanResult
-> Operational projections

The same production truth should be reusable across multiple application surfaces.

Do not recalculate independent production truth in each UI.

## Compatibility / Requirements

Builder knows food properties.

The business module knows recipient requirements.

The compatibility / application layer determines which demand can consume standard production and which demand requires a production variant.

Do not hardcode gluten, lactose, timbal, department, Alt1, Alt2, crew, shift, VIP, salad, mash, tomato, spaghetti, macaroni or similar business terms into Planera Core.

Those are adapter, application or downstream operational concepts.

## Planning Slice

A Planning Slice is a thin orchestration/input concept representing one real service or Dish context plus demand and destinations that must be supplied.

It is not a new canonical persistence model or source of truth.

Do not create a parallel persistent Planning Slice database or domain unless a future locked decision explicitly requires it.

Planera Core input should remain generic around:

- baseline and demand
- units and destinations
- deviations, requirements and variants
- context and references

## Production Requirement Traceability

Production Requirement / PlanResult must retain stable references back to the context that produced it where available.

Examples:

- service or event
- menu or publication
- Dish or composition_id
- destination or unit
- business context identifiers
- review / requirement references where appropriate

These references support downstream consumers such as Page3, packing, recipe scaling, prep, freezer, history and analytics.

Planera does not take ownership of the referenced Builder or business objects.

## Result Reuse

PlanResult is not only a Page3 value.

The same production truth should be consumable by:

- Produktionsunderlag
- destination breakdowns
- packing projections
- dashboard summaries
- print
- future recipe scaling
- prep
- freezer pull
- purchasing
- history
- analytics

Presentation layers may group or filter the result differently, but must not create a competing production calculation.

## Kommun Production Track

Kommun production flow is:

Published Menu
-> department menu choices
-> recipient requirement cohorts
-> Page2 human review
-> meal orchestration
-> review-aware Kommun adapter
-> production acceptance
-> Planera 2.0 Core
-> Page3 production underlay

This track is about standard production and recipient-specific adapted production.

A demanded option requires current completed review before it contributes production truth.

A zero-demand published option does not require review and must not invent production.

Missing destination menu choice remains explicit.

## Specialkost Semantics

Specialkost is recipient-level or recipient-cohort information that may affect what food must be produced.

Examples:

- one recipient never tomato
- gluten-free
- timbal
- vegetarian
- no fish

These belong in canonical requirements / cohorts.

After human review they may become Planera deviations.

Specialkost is part of the production track.

## Serveringsanpassning Semantics

Serveringsanpassning is a different domain.

It describes destination / department-level serving, packing or delivery rules.

Examples:

- salad for 6
- the department never wants tomato in its salad
- sauce separately
- mashed potato instead of boiled potato
- macaroni instead of spaghetti

Serveringsanpassning does not become Specialkost merely because it can affect final packing.

It must not be inserted into the default normal/specialkost production worklist.

## Scope Determines Domain

A similar phrase can belong to different tracks depending on scope.

Example:

One recipient never tomato:
-> Specialkost
-> requirement cohort
-> Page2 review
-> possible adapted production

Whole department wants salad without tomato:
-> Serveringsanpassning
-> separate serving / packing flow

This distinction is locked.

## Requirement Group / Cohort Semantics

- one DepartmentRequirementGroup represents one exact recipient cohort
- cohort requirements may contain 1..N atomic requirement keys
- quantities between groups are mutually exclusive within one destination and service context
- a multi-requirement recipient belongs to one combined group, not multiple overlapping groups
- group quantity is counted once regardless of number of requirement keys
- recipients outside requirement groups remain in standard baseline production
- sum of active effective cohort quantities must not exceed destination baseline
- Planera Core may rely on adapter/application input already satisfying this contract
- Core remains unaware of Kommun/person-specific concepts
- aggregate cohort persistence does not store recipient identities; disjointness is a business invariant in Yuplan 1.0

## Human Review Semantics

Persisted review answers:

> Does this current published dish require an adaptation for this semantic recipient cohort?

Review truth is distinct from quantity truth.

Review does not own:

- current baseline
- current group quantity
- current requirement keys
- current destination assignment

UNREVIEWED is not equivalent to no deviations.

A stale review cannot become current production truth.

Serveringsanpassningar do not enter this review simply because they may later appear in packing.

## Servering / Packing Track

Servering / packing is a separate operational track.

Conceptually:

Published menu / Builder components
+ destination serving rules
-> Serveringsanpassning Resolver
-> serving / packing projection

This track may use the same date, meal, menu and destination context as production, but it must remain semantically separate.

The production cook should be able to work with a clean normal/specialkost production view without all serving preferences being present.

## Menu-Aware Servering Resolver

A structured serving resolver belongs outside Planera Core.

It may combine:

- current published menu
- canonical Builder component identities
- current destination / department
- serving rules
- quantities

to determine what is actually relevant for the current service.

Example:

Rule:
- boiled potato OR pasta -> mashed potato

If today's dish already contains mashed potato:
- no extra mash requirement

If today's dish contains boiled potato:
- replacement requirement may be created

Do not implement this through free-text string matching when canonical Builder structure exists.

## Open User-Defined Serving Rules

The long-term model must support more than Mos/Sallad/Ovrigt.

Users must eventually be able to define structured:

- additions
- destination-level exclusions
- conditional component substitutions
- serving / handling instructions

Examples:

- boiled potato -> mashed potato
- pasta -> mashed potato
- spaghetti -> macaroni
- rice -> potato
- sauce separately
- no tomato in department salad

Do not hardcode these examples into Core.

## Packing / Distribution

Packing is a downstream operational projection.

It may consume:

- Planera 2.0 production truth
- destination breakdown
- Specialkost output
- resolved Serveringsanpassning output

Do not create a second packing calculation engine.

Do not collapse the underlying domains merely because a packing UI combines them.

## Optional Combined Total Pack List

A combined destination-oriented pack list is allowed and desirable when explicitly selected by the user.

Example:

Solrosen — Avdelning 1

- Normalkost: 8
- Timbal: 1
- Sallad: 6 — aldrig tomat
- Potatismos istället för kokt potatis: 1

This can be projected for:

- one department
- one delivery location / boende
- all departments

The combined list is downstream presentation.

It does not make Serveringsanpassning part of Specialkost or the default production worklist.

## Destination Hierarchy

Do not assume department == final delivery location forever.

Future packing may support:

delivery location / boende
-> departments
-> packed items

while production planning may remain:

meal option / dish
-> departments
-> recipient cohorts

Stable destination references must therefore be preserved.

## Future Capabilities Above Core

- recipe and yield scaling
- prep
- freezer pulls
- purchasing
- Husk att bestill
- packing and distribution
- Serveringsanpassning resolution
- planned vs produced vs consumed
- waste
- historical consumption
- forecasts
- analytics
- AI recommendations

Do not build these systems into Planera Core.

## Kommun Integration Strategy

- retain existing current production behavior initially
- run Planera 2.0 in parallel with Planera 1
- prove unit baselines, deviations, totals and destinations
- compare production parity separately from serving parity
- preserve current fixed Serveringstillägg during transition
- classify differences as regression, legacy limitation or intentional improvement
- only switch production truth after parity is accepted

Production parity must not require Serveringsanpassningar to be mixed into the normal/specialkost production list.

## Offshore Later Use

Offshore later uses the same Planera Core through its own adapter:

- POB
- shifts
- visitors
- crew requirements
- effective Work Menu

Operational projections may differ by business module while the production engine remains shared.

## Absolute Rules

- no separate production engine per module
- no Builder persistence inside Planera Core
- no Kommun domain language hardcoded into Core
- no UI-driven domain redesign
- no recipe, inventory, forecast or AI system inside Core
- no duplicate production calculation in Page3 / packing UI
- no hardcoded Mos/Sallad/Tomato/etc. rule system in Core
- no mixing Serveringsanpassning rows into the default normal/specialkost production worklist
- a combined total pack list may combine outputs only as an explicit downstream projection

## Detailed Kommun Operational Reference

See:

`docs/planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md`
