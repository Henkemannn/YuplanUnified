Status: LOCKED
Last reviewed: 2026-09-23

# Planera 2.0 Architecture Lock

## Purpose

Planera 2.0 is a generic production engine.

Core question:

> What needs to be produced?

The wider Planera application layer may also project that production truth into operational outputs such as packing, prep, freezer pulls and later purchasing, but those are not separate production engines.

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
  -> packing / prep / freezer / purchasing / history / analytics

The same Planera production result should be reusable by multiple application surfaces.

Do not recalculate independent production truth separately in each UI.

## Compatibility / Requirements

Builder knows food properties.

Example: Dish Kottbullar contains Components whose metadata may imply gluten and milk or lactose-related properties.

Business module knows recipient requirements.

Example: Department A has recipients requiring gluten-free, lactose-free, both, texture adaptations, etc.

The compatibility or application layer determines which demand can consume standard production and which demand requires a production variant.

Do not hardcode gluten, lactose, timbal, department, Alt1, Alt2, crew, shift, VIP, salad, mash, tomato, spaghetti, macaroni or similar business terms into Planera Core.

Those are adapter, application or operational-projection concepts.

## Planning Slice

A thin orchestration and input concept representing one actual service or Dish context plus demand and destinations that must be supplied.

It is not a new canonical persistence model or source of truth.

Do not create a parallel persistent Planning Slice database or domain unless a future locked decision explicitly requires it.

Planera Core input should remain generic around:
- baseline and demand
- units and destinations
- deviations, requirements, and variants
- context and references

## Production Requirement Traceability

Production Requirement / PlanResult must retain stable references or identity back to the context that produced it where available.

Examples of references may include:
- service or event
- menu or publication
- Dish or composition_id
- destination or unit
- business context identifiers
- review / requirement references where appropriate

These references exist for traceability and downstream consumers such as packing, recipe scaling, prep, freezer, history and analytics.

Planera does not take ownership of the referenced Builder or business objects.

Planera Core output must be capable of expressing:
- what production requirement the result belongs to
- quantity
- requirement or variant grouping
- destination and unit breakdown
- warnings

## Result Reuse

PlanResult is not only a Page3 value.

The same production truth should be consumable by:
- Produktionsunderlag
- packing / distribution
- dashboard summaries
- print
- future recipe scaling
- prep
- freezer pull
- purchasing
- history
- analytics

Presentation layers may group or filter the result differently, but must not create a competing calculation truth.

## Kommun First Use Case

- normalkost is the standard production baseline for the chosen Dish or menu option.
- department resident counts are demand.
- recipient dietary or texture requirements are business requirements.
- the human review determines who cannot consume the standard production as published.
- Planera calculates normal quantity plus adapted production quantity and destination breakdown.

Example user-facing result:

Köttbullar:
- 87 standard portions
- 2 gluten adaptations -> Department A
- 3 lactose adaptations -> Departments B and C
- 1 gluten plus lactose adaptation -> Department D

Normalkost, specialkost, timbal, department, Alt1 and Alt2 are Kommun language, not Core language.

The current temporary form="unspecified" / historical specialkost form fallback is not authoritative long-term form semantics and must not define Core.

## Kommun Product2 Flow

The intended first complete Kommun flow is:

Builder Published Menu
-> Department menu choices
-> Product2 Page1
-> Product2 Page2 human review
-> meal-level orchestration
-> review-aware Kommun adapter
-> production acceptance
-> Planera 2.0 Core
-> Page3 production underlay
-> downstream operational projections

Missing destination menu choice remains explicit.

A zero-demand published option does not require review and must not invent production.

A demanded option requires current completed review before it contributes production truth.

## Requirement Group / Cohort Semantics

- one DepartmentRequirementGroup represents one exact recipient cohort
- cohort requirements may contain 1..N atomic requirement keys
- quantities between groups are mutually exclusive within one destination and service context
- a multi-requirement recipient belongs to the combined group, not to each individual requirement group separately
- group quantity is counted once regardless of how many requirement keys the group contains
- recipients not assigned to any requirement group remain in standard baseline production
- the sum of active effective cohort quantities must not exceed the destination baseline
- Planera Core may rely on adapter/application input already satisfying this cohort contract
- Planera Core must remain unaware of Kommun/person-specific concepts
- the aggregate cohort model does not persist recipient identities, so overlap detection is a business data invariant in Yuplan 1.0
- future recipient-level persistence could verify cohort disjointness automatically, but it is not required for MVP

## Human Review Semantics

Human review truth is distinct from quantity truth.

Persisted review answers:

> Does this current published dish require an adaptation for this semantic recipient cohort?

Review does not own:
- current baseline
- current group quantity
- current requirement keys
- current destination assignment

Those remain current business truth.

UNREVIEWED is not equivalent to no deviations.

A stale review cannot become current production truth.

## Standing Operational Needs

Kommun already has recurring Serveringstillägg.

Those current fixed additions are valid transition input and must not be discarded during Planera 2.0 adoption.

Long-term, standing operational needs should support structured:
- additions
- exclusions
- conditional substitutions
- serving / handling instructions

Examples:
- salad for 5
- never tomato
- boiled potato -> mashed potato
- pasta -> mashed potato
- spaghetti -> macaroni
- sauce separately

These concepts must remain user-extensible and must not be hardcoded into Planera Core.

## Menu-Aware Standing-Needs Resolution

A structured standing-needs resolver belongs outside Core.

It may combine:
- current published menu
- canonical Builder component identities
- current destination / department
- standing operational rules
- quantities / cohorts

to determine what is actually relevant for the current service.

Example:

Standing rule:
- boiled potato OR pasta -> mashed potato

If today's published dish already contains mashed potato:
- no additional mashed-potato requirement is created

If today's dish contains boiled potato:
- a replacement requirement may be created

Do not implement menu-aware substitutions through free-text string matching when canonical Builder component structure is available.

## Packing / Distribution

Packing and distribution are operational projections above Core.

The required principle is:

Production truth
+ destination traceability
+ resolved standing operational needs
-> pack-oriented output

A Kommun daily packing projection should be able to answer:
- what item / variant
- quantity
- date / meal
- destination / department
- source requirement / standing need
- handling note where relevant

Do not create a second packing calculation engine.

Do not assume department must remain the final delivery location forever.

Future hierarchy may be:

delivery location / boende
-> departments
-> packed items

while planning remains:

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
- standing operational needs
- planned vs produced vs consumed
- waste
- historical consumption
- forecasts
- analytics
- AI recommendations

Do not build those systems into Planera Core.

## Kommun Integration Strategy

- retain existing current production behavior initially
- run Planera 2.0 in parallel with Planera 1
- use existing comparison and parity mechanisms
- prove unit baselines, deviations, totals and destinations
- preserve current fixed Serveringstillägg during transition
- classify differences as regression, legacy limitation or intentional improvement
- only switch production truth after parity is accepted

Example of an intentional future difference:

Planera 1 may always output a fixed Mos count.
A menu-aware Planera operational layer may output a smaller replacement count when today's published menu already contains mash.

Numerical parity is therefore not the only acceptance criterion; semantic correctness matters.

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
- do not begin broad operational features before the current production contracts are verified

## Detailed Kommun Operational Reference

See:

`docs/planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md`
