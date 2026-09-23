# Kommun Standing Needs, Serveringstillägg och Packning

Status: ACTIVE PRODUCT DIRECTION
Last reviewed: 2026-09-23

## Purpose

This document captures the intended development direction for Kommun operational needs around:

- specialkost / dietary and texture requirements
- standing serving additions
- exclusions and preferences
- component substitutions
- daily production output
- packing and distribution per destination

The end product is not only a production total. A kitchen must be able to answer, for every service day and meal:

> What should be produced, what should be packed, how much, and to which department / delivery destination?

This document is a detailed implementation reference. Ground Truth remains authoritative where the two differ.

## Existing Kommun V1 behavior

Kommun already has a useful V1 concept called Serveringstillägg.

Current persistence:
- `service_addons`
- `department_service_addons`

Current addon master rows are site scoped and have:
- name
- family
- active state

Current families are:
- `mos`
- `sallad`
- `ovrigt`

A department binding can hold:
- lunch_count
- dinner_count
- note

Current Planera 1 behavior aggregates positive counts per site and meal and preserves department breakdown plus note text.

Example:

- Department A: Mos 4, note "Aldrig tomat"
- Department B: Mos 3

Current result:
- Mos total 7
- Department A 4
- Department B 3

This is useful and must not be discarded during Planera 2.0 migration.

## Problem with the current model

The existing model stores mostly fixed counts and free-text notes. It does not understand why an addon exists or whether the published menu already satisfies the need.

Examples:

- "Mos 1" is currently a fixed recurring count, not "replace today's potato/pasta component with mash when needed".
- "Aldrig tomat" is text; Yuplan cannot decide whether today's menu contains tomato.
- "Sås separat" is operational handling, not the same semantic type as "extra salad".
- A replacement can currently be represented only by naming an addon, not by describing the condition under which it applies.

The modernization must therefore preserve existing data while adding structured meaning.

## Product principle

Do not hardcode a fixed catalog such as only Mos, Sallad or Sauce.

Users must be able to define operational needs around any relevant menu component.

Examples:
- boiled potatoes -> mashed potatoes
- pasta -> mashed potatoes
- spaghetti -> macaroni
- rice -> potatoes
- standard sauce -> sauce separately
- salad -> salad without tomato
- garnish -> omit parsley
- bread -> gluten-free bread
- any other future component replacement

The system should be open to new component identities without code changes in Planera Core.

## Four standing-need concepts

The long-term Kommun model should distinguish at least four semantic types.

### 1. Standing addition

Something should be packed in addition to the standard menu.

Examples:
- salad for 5
- bread for 3
- extra sauce for 2

### 2. Exclusion

A component or ingredient should not be present for a recipient cohort.

Examples:
- never tomato
- never carrot
- no parsley

The rule should only become operationally active when the current published menu actually contains or implies the excluded item.

### 3. Conditional substitution

When a particular component is present, replace it with another component.

Examples:
- boiled potato -> mashed potato
- pasta -> mashed potato
- spaghetti -> macaroni

A substitution rule must not create duplicate production when the desired replacement is already the normal published component.

Example:

Standing rule:
- boiled potato OR pasta -> mashed potato, quantity 1

Published menu A:
- meatballs
- boiled potato
- gravy

Resolved operational need:
- 1 mashed potato replacement

Published menu B:
- meatballs
- mashed potato
- gravy

Resolved operational need:
- no extra mashed potato
- replacement is already satisfied by the published menu

### 4. Serving / handling instruction

The food is not necessarily different, but must be packed or handled differently.

Examples:
- sauce separately
- garnish separately
- do not mix components
- extra container

These should remain traceable into packing output.

## Relation to specialkost

Specialkost and standing operational needs are related but are not the same concept.

Specialkost / requirement cohorts answer:
> Which recipients cannot consume the standard dish as published?

Standing needs answer:
> What recurring additions, exclusions, substitutions or handling rules must also be considered for this destination?

For Yuplan 1.0, the existing department specialkost registration can remain as an input surface while adapters translate it into canonical requirement cohorts.

A full rewrite of the department UI is not required before Planera 2.0 can become the production engine.

Longer term, the registration UI should move toward structured atomic requirements and explicit cohort combinations instead of an ever-growing catalog of combined specialkost names.

## Canonical menu knowledge

Menu-aware rules must resolve against canonical Builder knowledge, not against menu text heuristics.

Preferred flow:

Builder
-> Components
-> Dish / Composition
-> Published Menu
-> current option assignment
-> standing-needs resolver
-> Planera / operational requirements
-> production and packing projections

Do not implement rules such as:

`if "potatismos" in menu_text`

Instead, use stable component or semantic identities where available.

The Builder layer owns food identity and composition. The Kommun business layer owns recipient and destination needs.

## Resolver responsibility

A menu-aware Standing Needs Resolver should sit outside Planera Core.

It receives:
- current published menu / option
- Builder component identities
- destination / department
- standing needs for that destination
- quantities / cohorts

It determines which standing rules are relevant for this service.

Examples:
- no tomato + no tomato in today's menu -> no action
- no tomato + tomato in today's salad -> operational variant required
- potato->mash + today's starch is potato -> replacement required
- potato->mash + today's starch already mash -> no extra action

The resolver must not silently infer food structure from free text when canonical Builder structure exists.

## Planera 2.0 boundary

Planera 2.0 Core remains generic and answers:

> What needs to be produced?

Do not hardcode:
- tomato
- carrot
- mash
- salad
- spaghetti
- macaroni
- department
- Kommun-specific addon families

inside Core.

The Planera application / orchestration layers may combine:
- PlanResult from Core
- resolved standing operational needs
- destination context

into downstream projections such as production underlay and packing.

The current baseline/deviation model should not be overloaded to pretend that every standing addition or handling instruction is a dietary deviation.

Extend contracts deliberately when required.

## Daily packing output

A daily pack list is a required operational outcome for Kommun.

The pack list should be derivable per:
- site
- service date
- meal
- delivery location / boende where available
- department
- published option / dish
- component / production item
- requirement / variant
- standing need or substitution

Minimum useful row concept:

- destination_id
- destination display name
- service date
- meal
- option / dish reference
- item / component identity
- item display name
- quantity
- unit where known
- reason / source type
- requirement or standing-rule reference
- handling note where relevant

The same production truth may be projected differently:

Production view:
- what the kitchen must produce

Packing view:
- what each destination must receive

These are projections over shared canonical production / operational requirements, not separate calculation engines.

## Destination hierarchy

Do not assume department == final delivery location forever.

Future packing should support:

delivery location / boende
-> departments
-> packed items

while planning may remain:

meal option / dish
-> departments
-> requirement cohorts

The system must therefore retain stable destination references and allow later grouping without changing production truth.

## Example

Department A has baseline 8.

Standing needs:
- salad for 5
- 1 recipient never tomato
- 1 recipient: boiled potato or pasta -> mashed potato
- 2 recipients: sauce separately

Published lunch:
- fried fish
- boiled potato
- dill sauce
- carrot salad

After menu-aware resolution and Planera calculation, operational output may include:

Production:
- standard fish quantity
- any reviewed dietary adaptations
- mashed potato replacement 1
- salad quantity 5

Packing for Department A:
- normal meal quantities
- 1 mashed potato instead of boiled potato
- 5 salad portions
- 2 sauce-separate packs
- no tomato-specific action because today's salad contains no tomato

Next day, if the published starch is already mashed potato:
- do not add a second mashed-potato quantity for the substitution rule

## User-defined openness

Administrators must eventually be able to create and maintain standing operational rules without developer changes.

The UI should guide the user into structured data, not arbitrary programming.

A future editor can conceptually allow:

Type:
- addition
- exclusion
- substitution
- handling instruction

Applies to:
- lunch
- dinner
- selected services / future scope

Target:
- choose canonical component / role / semantic category

Replacement:
- optional canonical component

Quantity:
- fixed count or cohort-linked quantity

Note:
- human-readable operational note

The first implementation may support a deliberately smaller subset, but the data model and resolver must not lock Yuplan to only Mos/Sallad/Ovrigt.

## Migration from current Serveringstillägg

Do not delete the existing V1 tables or UI as part of Planera 2.0 cutover.

Recommended migration strategy:

1. Keep existing `service_addons` and `department_service_addons` working.
2. Expose their existing fixed counts in Planera 2.0 operational / packing projections.
3. Classify or map obvious existing addon families where safe.
4. Keep free-text notes visible to operators.
5. Introduce structured standing-need rules separately or by a deliberate migration.
6. Convert legacy rows only when semantics are explicit; do not guess from names or notes.
7. Run parity against current production-list behavior.
8. Gradually promote structured rules to canonical truth.

## Specialkost modernization

Current specialkost administration contains legacy combined categories and names.

Direction:
- atomic requirement definitions
- exact disjoint recipient cohorts
- multi-requirement recipients represented as one combined cohort
- service-specific quantity overrides
- human Page2 review against the actual published dish
- no automatic interpretation of combined legacy names as canonical truth without an explicit migration rule

The existing department registration surface may remain during Yuplan 1.0 transition.

The architecture must support later UX modernization without forcing another production-engine rewrite.

## Parity and cutover

Planera 1 and Planera 2.0 should run in parallel during Kommun cutover.

Compare separately:
- department baselines
- menu choices
- requirement quantities
- standard production
- adapted production
- destination breakdown
- existing service-addon totals
- packing projections

Differences are not automatically bugs.

Example:
Planera 1 may always output Mos 7 because it is a fixed recurring addon.
Planera 2.0 may later correctly output Mos 3 because four recipients already receive mash in the published dish.

Such differences must be classified as:
- regression
- legacy limitation
- intentional improved behavior

before cutover.

## MVP / rollout boundary

For Kommun 1.0 Ready for Pilot:

Required:
- canonical published menu
- department menu choices
- current baseline quantities
- canonical requirement cohorts
- human review
- Planera 2.0 production result
- production underlay / Page3
- Planera 1 vs Planera 2 parity
- daily destination-aware packing output
- existing fixed Serveringstillägg preserved in that operational output

Architecture-required but allowed to mature after the first pilot if necessary:
- arbitrary menu-aware component substitution editor
- full structured migration of all free-text addon notes
- advanced delivery-location hierarchy
- recipient-level identities
- advanced ingredient/allergen reasoning
- inventory / purchasing / freezer integration

The MVP must not block future arbitrary substitutions by hardcoding only today's addon families.

## Non-goals

Do not turn this work into:
- inventory
- purchasing
- recipe management
- AI recommendation engine
- person-level care record
- free-text NLP rules
- a second production engine

The central rule remains:

> Builder describes the food. Kommun describes recipient and destination needs. Planera calculates production. Operational projections turn that truth into usable daily work, including packing.
