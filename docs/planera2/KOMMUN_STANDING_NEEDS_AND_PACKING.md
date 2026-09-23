# Kommun Specialkost, Serveringsanpassningar och Packning

Status: ACTIVE PRODUCT DIRECTION
Last reviewed: 2026-09-23

## Purpose

This document captures the intended Kommun direction for three related but deliberately separate operational tracks:

1. Specialkost / recipient requirements
2. Serveringstillägg / serveringsanpassningar
3. Packing projections

The distinction is product-critical.

The kitchen must be able to work with a clean production flow for normal production and specialkost without being forced to see all serving preferences at the same time.

At the same time, Yuplan must later be able to generate a complete pack-oriented view for a chosen department or for all departments when the user explicitly wants that combined view.

Ground Truth remains authoritative where this document differs.

---

## Core separation

### Specialkost

Specialkost is recipient-level or recipient-cohort information that can affect what food must be produced.

Examples:

- one person never eats tomato
- gluten-free
- timbal
- vegetarian
- no fish
- gluten + lactose combination

Specialkost belongs in the requirement / cohort model.

It enters the Product2 review flow and may create adapted production through Planera 2.0.

Conceptually:

Department recipient requirements
-> Page2 human review against today's published dish
-> Planera 2.0
-> normal production + specialkost production

### Serveringstillägg / Serveringsanpassning

Serveringsanpassning describes how a department wants food delivered, packed or served.

Examples:

- the department wants salad for 6
- the department never wants tomato in its salad
- sauce separately for 2
- mashed potato instead of boiled potato
- mashed potato instead of pasta
- macaroni instead of spaghetti
- omit a garnish for the department

This information is not automatically specialkost and must not pollute the normal/specialkost production worklist.

Conceptually:

Department serving rules
+ today's published menu
-> serving resolver
-> serving / packing projection

### Important tomato example

These two cases are intentionally different:

**One person never wants / cannot have tomato**
-> register as Specialkost
-> appears in the specialkost requirement flow
-> may require Page2 review and adapted production.

**A whole department never wants tomato in its salad**
-> register as Serveringsanpassning
-> does not appear as a specialkost row
-> appears only in the serving / packing surface when relevant.

This distinction must remain explicit in data, orchestration and UI.

---

## Current Kommun V1 behavior

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

This existing capability is useful and should be preserved during migration, but its semantics are too coarse for the long-term model.

---

## Problem with the current Serveringstillägg model

The existing model stores mostly fixed counts and free-text notes.

It does not understand why a row exists or whether today's published menu already satisfies the rule.

Examples:

- "Mos 1" is currently a fixed recurring count, not "replace today's potato/pasta component with mash when needed".
- "Aldrig tomat" is text; Yuplan cannot decide whether today's salad actually contains tomato.
- "Sås separat" is a handling instruction, not the same semantic type as extra salad.
- A replacement can currently only be approximated by naming an addon.

The modernization should preserve existing data while adding structured meaning.

---

## Serveringsanpassning: long-term semantic types

The long-term model should support at least these serveringsanpassning types.

### 1. Standing addition

Something should be packed in addition to the normal meal.

Examples:

- salad for 5
- bread for 3
- extra sauce for 2

### 2. Department-level exclusion

A component or ingredient should be omitted from the department's serving.

Examples:

- no tomato in this department's salad
- no carrot in this department's salad
- omit parsley garnish

This is department-level serving behavior.

If the same rule applies only to one recipient, it belongs in Specialkost instead.

### 3. Conditional component substitution

When a particular component is present, replace it with another component.

Examples:

- boiled potato -> mashed potato
- pasta -> mashed potato
- spaghetti -> macaroni
- rice -> potato

The substitution catalog must be open.

Do not hardcode only current examples.

### 4. Serving / handling instruction

The food is not necessarily different, but must be packed or handled differently.

Examples:

- sauce separately
- garnish separately
- do not mix components
- extra container

---

## User-defined openness

Administrators must eventually be able to define serving rules without code changes.

The model must not be limited to:

- Mos
- Sallad
- Ovrigt

A future editor can conceptually support:

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
- canonical component
- component role
- semantic component category

Replacement:
- optional canonical component

Quantity:
- fixed count
- future rule-linked quantity

Note:
- human-readable operational note

The first implementation may support a smaller subset, but the architecture must remain open.

---

## Canonical menu knowledge

Menu-aware serving rules must resolve against canonical Builder knowledge, not menu-text heuristics.

Preferred flow:

Builder
-> Components
-> Dish / Composition
-> Published Menu
-> current option assignment
-> Serveringsanpassning Resolver
-> serving / packing projection

Do not implement rules such as:

`if "potatismos" in menu_text`

when a canonical component identity exists.

Builder owns food identity and composition.

Kommun owns recipient requirements, destination needs and serving rules.

---

## Menu-aware substitution example

Standing department rule:

- boiled potato OR pasta -> mashed potato
- quantity 1

Published menu A:

- meatballs
- boiled potato
- gravy

Resolved serving need:

- 1 mashed potato instead of boiled potato

Published menu B:

- meatballs
- mashed potato
- gravy

Resolved serving need:

- no additional mashed potato
- the desired component is already the normal published component

The system must not create duplicate mash production or duplicate packing.

The same principle applies to:

- spaghetti -> macaroni
- tomato exclusions
- carrot exclusions
- any future user-defined component rule

---

## Specialkost production flow

The Product2 flow currently under construction remains focused on production truth.

It should stay visually clean.

Conceptually:

Published menu
-> department menu choices
-> canonical requirement cohorts
-> Page2 human review
-> meal orchestration
-> Planera 2.0
-> Page3 production underlay

Page3 production views should focus on:

- normal production
- specialkost / adapted production
- destination breakdown
- production readiness

Serveringsanpassningar should not be inserted as ordinary specialkost rows in this flow.

The cook producing today's lunch should not be forced to process salad / serving-preference information merely to understand normal vs special production.

---

## Serveringsanpassning flow

Serveringsanpassningar should be available through their own operational surface.

Conceptually:

Published menu / Builder components
+ department serving rules
-> Serveringsanpassning Resolver
-> serving / packing projection

Potential Planera navigation later may include a separate surface such as:

- Översikt
- Normalkost
- Specialkost
- Servering / Packning

Exact naming and UI are deferred.

The critical rule is separation, not the final tab label.

---

## Production list cleanliness

Default production-oriented views must not become a mixed worklist containing:

- normal production
- specialkost
- salad counts
- serving notes
- sauce separately
- department component substitutions

all at once.

These are different operational tasks.

The user must be able to focus on the task currently being performed.

Examples:

**Cook / production view**
- 73 normal portions
- 4 timbal
- 2 gluten adaptations

**Serving / packing view**
- Department A: salad 6, never tomato
- Department B: sauce separately 2
- Department C: mashed potato instead of boiled potato 1

The two surfaces may derive from the same date, meal, menu and destinations while remaining separate operational projections.

---

## Optional combined total pack list

Later, Yuplan should also support an explicitly chosen **total pack list**.

This is not the default production list.

It is a combined destination-oriented projection that merges the relevant outputs when the user asks for it.

Example:

### Solrosen — Avdelning 1

- Normalkost: 8
- Timbal: 1
- Sallad: 6
  - aldrig tomat
- Potatismos istället för kokt potatis: 1

This view can be generated:

- for one selected department
- for one delivery location / boende
- for all departments

The combined view is valuable during final packing because the operator wants one complete destination picture.

It must not become the calculation source of truth.

It is a projection that combines:

- Planera 2.0 production result
- destination breakdown
- specialkost output
- resolved serveringsanpassningar

The underlying specialkost and servering domains remain separate.

---

## Daily pack list requirements

A daily pack list should be derivable per:

- site
- service date
- meal
- department / destination
- future delivery location / boende
- published option / dish
- standard production
- specialkost variant
- serving addition
- substitution
- handling instruction

Minimum useful row concept:

- destination_id
- destination display name
- service date
- meal
- item / component reference
- item display name
- quantity
- unit where known
- source type
- specialkost requirement reference where relevant
- serveringsanpassning reference where relevant
- note where relevant

Source type must preserve whether a row came from:

- standard production
- specialkost production
- serveringsanpassning

Do not flatten those semantics merely because they are displayed together in a total pack list.

---

## Destination hierarchy

Do not assume department == final delivery location forever.

Future packing should support:

delivery location / boende
-> departments
-> packed items

while production planning may remain:

meal option / dish
-> departments
-> requirement cohorts

Stable destination references must therefore be preserved.

---

## Example: separate operational views

Department A has baseline 8.

Recipient specialkost:
- 1 Timbal

Department serving rules:
- salad 6
- department salad never tomato
- 1 mashed potato instead of boiled potato
- sauce separately 2

Published lunch:
- meatballs
- boiled potato
- gravy
- mixed salad containing tomato

### Production / Specialkost view

- normal production for Department A: derived from Planera 2.0
- Timbal: 1

No salad or serving preference is inserted into the specialkost worklist.

### Servering / Packning view

- salad 6
- salad without tomato
- mashed potato instead of boiled potato 1
- sauce separately 2

### Optional total pack view for Department A

- Normalkost: 7
- Timbal: 1
- Sallad: 6 — utan tomat
- Potatismos istället för kokt potatis: 1
- Sås separat: 2

The exact future numbers and presentation depend on the resolved menu and production contracts, but the separation principle is locked.

---

## Relation to Planera 2.0 Core

Planera 2.0 Core remains generic and answers:

> What needs to be produced?

Specialkost adaptations can become Planera deviations after human review.

Serveringsanpassningar are not automatically Planera deviations.

Do not overload the baseline/deviation model simply to force every serving preference through Core.

A later serving resolver may identify a true additional production requirement, for example a component substitution that requires extra mash.

That operational requirement may then be connected to production through an explicit contract.

It must not be disguised as specialkost merely because both eventually affect packing.

---

## Migration from current Serveringstillägg

Do not delete the existing V1 tables or UI during Planera 2.0 cutover.

Recommended migration strategy:

1. Keep `service_addons` and `department_service_addons` working.
2. Keep current fixed counts available in the separate Servering / Packning surface.
3. Keep notes visible to operators.
4. Do not inject them into the normal/specialkost Page2 production worklist.
5. Introduce structured serveringsanpassning rules deliberately.
6. Convert legacy rows only when semantics are explicit.
7. Do not guess semantics from names or free-text notes.
8. Run parity against current serveringstillägg totals.
9. Later allow menu-aware structured rules to replace coarse fixed addons.

---

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

Important:

A recipient preference / restriction such as "never tomato" belongs in this specialkost track when it applies to a person or recipient cohort.

Do not move recipient-level needs into Serveringsanpassning merely because a similar department-level serving rule can exist.

---

## Parallel run and parity

Planera 1 and Planera 2.0 should run in parallel during Kommun cutover.

Compare production separately from serving.

### Production parity

Compare:

- department baselines
- menu choices
- specialkost / requirement quantities
- standard production
- adapted production
- destination breakdown

### Servering parity

Compare:

- current service-addon counts
- department breakdown
- notes
- future resolved serving rules

Do not require production parity to include serving preferences in the same list.

Differences are not automatically bugs.

A future menu-aware servering resolver may intentionally produce a different mash replacement quantity than today's fixed addon total because the published menu may already contain mash.

Classify differences as:

- regression
- legacy limitation
- intentional improved behavior

before cutover.

---

## MVP / rollout boundary

For Kommun 1.0 Ready for Pilot:

Required:

- canonical published menu
- department menu choices
- current baseline quantities
- canonical requirement cohorts
- human review
- Planera 2.0 production result
- Page3 production underlay with clean normal/specialkost focus
- Planera 1 vs Planera 2 production parity
- separate Servering / Packning access
- daily destination-aware packing output
- existing fixed Serveringstillägg preserved in that separate operational surface
- optional total pack projection may be added when operationally ready without changing production truth

Architecture-required but allowed to mature after first pilot if necessary:

- full arbitrary component-substitution editor
- complete conversion of all free-text notes to structured rules
- advanced delivery-location hierarchy
- recipient-level identities
- advanced ingredient/allergen reasoning
- inventory / purchasing / freezer integration
- polished combined total-pack UI

The MVP must not block future arbitrary substitutions by hardcoding only today's addon families.

---

## Non-goals

Do not turn this work into:

- inventory
- purchasing
- recipe management
- AI recommendation engine
- person-level care record
- free-text NLP rule engine
- a second production engine
- one giant mixed normal/special/servering worklist

The central principles are:

> Specialkost describes recipient production requirements.

> Serveringsanpassning describes destination-level serving and packing rules.

> They remain separate operational tracks.

> A total pack list may combine their outputs only as an explicit downstream projection.
