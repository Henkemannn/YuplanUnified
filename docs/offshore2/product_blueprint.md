# Yuplan Offshore 2.0 - Product Blueprint

## 1. Product Definition
Yuplan Offshore 2.0 is a new operational module for offshore installations. It is not implemented yet.

Offshore is the place where a cook turns a fixed menu cycle into a working plan for a whole offshore period. Builder remains the canonical source for menus, dishes, compositions, components, recipes, canonical text, and aliases. Planera 2.0 remains the generic production engine. Offshore sits between them and turns approved Builder menus plus local installation context into service planning, prep, freezer picks, reminders, handover, and period history.

Offshore is not:
- a second menu library
- a parallel dish system
- a duplicate production engine
- a name-matched identity system
- a full crew portal on day one

The user should experience Offshore as the place that answers:
- what will be served
- when it will be served
- how many portions are needed
- what must be prepped
- what must be taken from the freezer
- what must be ordered
- what the next shift needs to know

## 2. Old Prototype Lessons
The old Rigplan/Offshore prototype is product reference, requirement source, and historical lesson. It is not the architecture for the new module.

### What to keep as product ideas
- week-centric work surface
- lunch and dinner as operational outputs
- handover at the end of the period
- prep and freezer as separate but related workflows
- reuse of previous planning when the same cycle returns
- printable and readable planning

### What to simplify
- dashboard clutter
- daily detail clutter
- menu import flow complexity
- day ordering and navigation friction
- reminder handling
- portions editing

### What to rebuild from scratch
- the whole period model
- menu-cycle mapping
- version locking
- copy-forward logic
- period status transitions
- exact separation between original menu and actual planned output

### What belongs elsewhere
- canonical menu identity -> Builder
- components, recipes, calculations -> Builder
- normalized production math -> Planera 2.0
- text normalization and unresolved resolution -> Builder

### What to discard
- prototype-specific route clutter
- superuser/admin shell as Offshore product surface
- direct text-as-identity assumptions
- duplicate menu storage as a separate source of truth

## 3. User Journey

### First start
1. The user opens Offshore.
2. Offshore asks which installation or rig to work on.
3. The user confirms basic setup details.
4. The user chooses or inherits a four-week menu cycle.
5. Offshore connects Builder menus to the cycle weeks.
6. The user sets standard portion counts for the installation.
7. Offshore creates the first planning period.
8. The user sees an empty but structured dashboard and can start filling the plan.

### Return on the next trip
1. Offshore opens on the active installation and current period.
2. The correct menu weeks are already linked.
3. The cook sees the current day, the remaining period, and the next handover point.
4. Portion counts are prefilled but adjustable.
5. Offshore shows an initial production plan.
6. The cook adds or adjusts prep, freezer picks, reminders, and local notes.
7. Work is checked off during the period.
8. The outgoing cook leaves a structured handover for the next shift.

## 4. Main Navigation
Offshore v1.0 should have a small, practical navigation. It should not expose empty future tabs.

### Recommended main views
- Översikt
- Periodplan
- Menycykel
- Prep
- Frysplock
- Husk att bestill
- Handover
- Inställningar

### View purpose and scope

#### Översikt
- User question: Where are we in the period, and what matters today?
- Important information: current installation, current period position, today’s lunch and dinner, prep, freezer picks, reminders, handover notes.
- Main action: jump to the period plan or open today’s detail.
- Mobile: condensed cards and fast check-off.
- Desktop/iPad: full daily summary with visible side panels.
- Needed in v1.0: yes.

#### Periodplan
- User question: What does the whole period look like?
- Important information: all days in the period, meals, original menu, actual plan, portions, prep, freezer, reminders, notes, status.
- Main action: edit the day plan and confirm status.
- Mobile: single-day or collapsed-day mode.
- Desktop/iPad: Lunch/Kväll grid plus day detail drawer.
- Needed in v1.0: yes.

#### Menycykel
- User question: Which Builder menu belongs to which cycle week?
- Important information: cycle weeks, assigned Builder menu versions, lock state, unresolved rows.
- Main action: assign or replace the menu for a cycle week.
- Mobile: read-only summary and limited reassignment.
- Desktop/iPad: cycle matrix with week mapping.
- Needed in v1.0: yes.

#### Prep
- User question: What should be prepared before service?
- Important information: prep templates, prep tasks, deadlines, links to servings, status.
- Main action: create, copy, move, check off prep tasks.
- Mobile: task list and checkbox flow.
- Desktop/iPad: grouped by day and meal, with notes and reuse actions.
- Needed in v1.0: yes.

#### Frysplock
- User question: What must be thawed and when?
- Important information: freezer templates, freezer pulls, item, quantity, time out, service use, date, status.
- Main action: create or copy freezer pulls and mark them done.
- Mobile: quick list and status updates.
- Desktop/iPad: grouped by date and service.
- Needed in v1.0: yes.

#### Husk att bestill
- User question: What do we need to remember to order?
- Important information: shared reminders, deadline, linked day or meal, optional component, status.
- Main action: add or check off reminders.
- Mobile: checklist-style list.
- Desktop/iPad: reminder board grouped by deadline.
- Needed in v1.0: yes.

#### Handover
- User question: What must the next cook know?
- Important information: finished prep, freezer status, pending orders, deviations, open tasks, important dates.
- Main action: fill the handover summary and mark it ready.
- Mobile: checklist and note capture.
- Desktop/iPad: structured end-of-period summary.
- Needed in v1.0: yes.

#### Inställningar
- User question: What is the installation setup?
- Important information: rig/installation, rotation style, default portions, standard period settings, user access.
- Main action: configure the installation and defaults.
- Mobile: basic fields only.
- Desktop/iPad: full setup form.
- Needed in v1.0: yes, but limited.

## 5. Dashboard
The dashboard should feel like an operational cockpit, not a generic admin home.

### What it must answer immediately
- Where are we in the period?
- What happens today?
- What must be prepared?
- What must be taken from the freezer?
- Is there anything important for the next shift?

### Recommended layout
- Current installation and current period position
- Today’s lunch and dinner
- Next serverings
- Today’s prep tasks
- Today’s freezer pulls
- Order reminders approaching deadline
- Open handover notes
- Quick link to the full period plan

### Product note
The dashboard should avoid KPI-heavy administration. A cook needs a fast operational summary, not charts.

## 6. Period Plan
The period plan is the core work surface. The primary MVP view is a Lunch/Kväll grid. A document-like day detail view is secondary and supports editing, printing, and mobile use.

### Business interval
The first validated operating shape is:
- Friday dinner
- through the following Thursday dinner
- then Friday lunch and handover

This means the first period can cross two calendar weeks.

### Primary MVP grid
```text
Day       Lunch                  Kväll
Friday    -                      [dinner]
Saturday  [lunch]                [dinner]
Sunday    [lunch]                [dinner]
Monday    [lunch]                [dinner]
Tuesday   [lunch]                [dinner]
Wednesday [lunch]                [dinner]
Thursday  [lunch]                [dinner]
Friday    [handover lunch]       -
```

### Each cell should be able to show
- date
- original menu
- actual planned output
- changed indicator
- portions
- prep status
- freezer status
- reminders
- note
- detail link
- unresolved status

### Secondary day detail
The day detail view can show:
- date
- original menu
- planned override
- portions
- prep tasks
- freezer pulls
- reminders
- notes
- print-friendly summary

### Editing principle
The grid is the primary operational surface. The day detail is where the cook drills down and edits a single meal slot or day.

## 7. Menu Cycle and Versioning
Builder menu content and Offshore cycle assignment are different things.

### Builder Menu
Builder owns the canonical menu content:
- dish/composition identity
- text
- components
- recipes
- unresolved import handling
- versioned content

### Offshore Menu Cycle
Offshore owns the local usage of Builder menus:
- which Builder menu belongs to week 1, week 2, week 3, week 4
- how cycle weeks map to calendar weeks
- how an individual week can be replaced
- how a period can span two calendar weeks

### Suggested cycle configuration fields
- rotation_start_year
- rotation_start_week
- rotation_start_menu_index
- rotation_length

### Per meal slot projection fields
Each meal slot should be able to carry:
- source_calendar_year
- source_calendar_week
- source_cycle_index
- source_builder_menu_id
- source_builder_menu_version
- source_menu_row_id
- source_composition_id
- source_unresolved_text

### Version handling
When a period is created, it should lock to the Builder version chosen at creation or explicit refresh.

Recommended rule:
- draft period -> explicit refresh allowed
- planned / active / completed period -> version locked

### Unresolved rows
Unresolved rows must remain visible in Offshore.

### No Builder menu connected
Offshore should still open and show a structurally valid empty state. The user should be able to create the installation, define defaults, and prepare the cycle even before a Builder assignment exists.

## 8. Original versus Planned
This is a binding MVP requirement.

Offshore must always distinguish between:
- what the published or written menu says
- what the cook actually plans to serve

### Conceptual fields
- original_menu_id
- original_menu_version
- original_menu_row_id
- original_composition_id
- original_unresolved_text
- planned_composition_id
- planned_text_override
- deviation_note
- changed_by
- changed_at
- visibility

### Allowed modes
#### Follow original
No override.

#### Choose another Builder composition
The original stays visible, but the planned composition changes.

#### Local text override
Used when the right composition is not yet available or when the adjustment is local.

#### Unresolved original
Must stay visible and must not be silently replaced.

The original menu must never be overwritten by Offshore.

## 9. Portions
Portion counts are part of the operational truth.

### v1.0 behavior
- each installation has a standard portion count
- each period can override the standard count
- each date can override the period count
- each meal slot can override the date count
- both original and adjusted values remain visible
- changes can carry a reason
- changes are auditable

### Later needs
Later versions may add crew counts, night food, guest counts, special events, buffers, and waste history.

## 10. Prep
Prep is modeled in two layers.

### OffshorePrepTemplate
Reusable knowledge. Suggested fields:
- template_id
- tenant scope or site scope
- composition reference or component reference
- title
- description
- default timing
- default quantity and unit
- sort order
- instructions

### OffshorePrepTask
Concrete task in a period. Suggested fields:
- task_id
- period_id
- meal_slot_id
- template reference
- composition reference or component reference
- title
- description
- due date/time
- amount and unit
- status
- assigned user, optional
- source
- created metadata
- completed metadata

### Status
- todo
- in_progress
- done
- skipped

### Sources
- manual
- template
- copied_from_previous_period
- planera_suggestion

### v1.0 rule
The first version must support manual tasks, create-from-template, edit, move, check off, and copy-from-previous-period. Perfect automatic recipe generation waits.

## 11. Freezer
Freezer work uses the same template/instance principle.

### OffshoreFreezerTemplate
Reusable freezer knowledge. Suggested fields:
- template_id
- composition or component reference
- item name
- default quantity and unit
- default timing
- notes

### OffshoreFreezerPull
Concrete row for the current period and serving. Suggested fields:
- pull_id
- period_id
- meal_slot_id
- template reference
- item name
- quantity
- unit
- pull date/time
- use date/time
- status
- note
- source

### Status
- todo
- pulled
- not_needed

### v1.0 rule
The first version must support manual rows, create-from-template, copy-from-previous-period, edit, and check off.

## 12. Husk att bestill
This is a shared reminder list per installation or site. It is not a private note list per user.

### Suggested fields
- tenant_id
- site_id
- period_id, optional
- meal_slot_id, optional
- component_id, optional
- title
- note
- deadline, optional
- status
- created_by
- created_at
- completed_by
- completed_at

### Status
- open
- done
- cancelled

### Product examples
- glutenfritt bröd
- extra mjölk till crew change
- färsk fisk till torsdag
- kontrollera burgare i frys
- specialkostprodukt

Supplier integration waits.

## 13. Handover
Handover is the structured transfer to the next cook.

### It should capture
- finished prep
- remaining prep
- fridge and freezer status
- made orders
- missing items
- menu deviations
- open tasks
- comments for the next period
- special diet information at the operational level
- important information for the incoming cook

### v1.0 shape
Start with a structured checklist plus free text note.

Later it can be signed, locked, sent, exported, and acknowledged by the next cook.

## 14. History and Reuse
When the same menu cycle returns, Offshore should help the cook start from the last good period.

### Main principle
Copy as a new draft.

### What should be reusable
- previous period plan
- previous actual plan
- previous prep tasks
- previous freezer pulls
- previous reminders
- previous portion overrides
- previous notes
- previous handover

### What should not happen
The old period must not be edited in place. It must stay historical.

## 15. Virtual Cooks
The old concept of Kokk 1-6 is valid as a future scheduling idea, but it is not blocking the first period model.

### Decision
Virtual cook positions are a valid future concept, but they are not required for the first MVP.

### Future concepts
- OffshoreVirtualCook
- OffshoreCookAssignment

### Suggested validity fields
- valid_from
- valid_to

OffshorePeriod should be able to exist with a responsible Unified user, a virtual cook position, both, or neither in draft mode.

## 16. Turnus versus Menu Cycle
These are separate concepts.

### Turnus
When people work.

### Menu cycle
Which menu applies to a week.

### Offshore period
Which days and service events are planned.

They must not be modeled as one thing.

The first MVP does not need a full personnel scheduling system.

## 17. Dashboard Details
The dashboard must answer:
- Which installation is active?
- Which period is active or upcoming?
- What is served today?
- What must be prepped?
- What must be taken from the freezer?
- What must be ordered?
- Is there anything important for the next shift?

The dashboard is an operational work area, not a KPI dashboard.

## 18. Navigation for MVP
Recommended main navigation:
- Översikt
- Periodplan
- Menycykel
- Prep
- Frysplock
- Husk att bestill
- Handover
- Inställningar

Roll-based admin functions can live elsewhere.

The foundation ticket may show disabled or coming-later states only where real content does not yet exist.

## 19. Print
Browser print is enough for MVP.

Later the print view should show:
- period information
- Lunch/Kväll grid
- original menu
- actual plan
- portions
- prep
- freezer pulls
- reminders
- handover

PDF or DOCX can wait.

## 20. Offline and Reliability
Full offline is not part of MVP.

The architecture should still allow:
- local cache of active period
- queued check-offs
- sync status
- conflict warning
- print as fallback

Document this as a future architecture requirement, not as current implementation.

## 21. Roles and RBAC
Minimum roles:

### Offshore admin or manager
- installation settings
- menu cycle
- standard portions
- user access
- publication and locking decisions

### Offshore cook or editor
- period planning
- actual overrides
- prep
- freezer pulls
- reminders
- handover

### Offshore viewer
- read-only period
- menu
- status

Future crew portal scope is separate.

All queries must follow Unified tenant/site security.

## 22. Domain Proposals
Document these, but do not implement them yet.

### OffshoreInstallation
- purpose: installation or rig context
- owner: Offshore
- key fields: installation name, tenant, site, time zone, status
- tenant/site scope: yes
- relation to Builder: anchor
- relation to Planera: anchor
- version semantics: settings versioned
- required in MVP: yes
- persisted or derived: persisted

### OffshoreMenuCycle
- purpose: reusable menu-cycle configuration
- owner: Offshore
- key fields: installation, cycle length, rotation start fields, lock state
- tenant/site scope: yes
- relation to Builder: references Builder menus and versions
- relation to Planera: input to production planning
- version semantics: yes
- required in MVP: yes
- persisted or derived: persisted

### OffshoreMenuCycleWeek
- purpose: one week in the cycle
- owner: Offshore
- key fields: cycle, week index, Builder menu reference, version lock, calendar mapping
- tenant/site scope: yes
- relation to Builder: references Builder menu/version
- relation to Planera: source for projection
- version semantics: yes
- required in MVP: yes
- persisted or derived: persisted or derived, depending on implementation

### OffshorePeriod
- purpose: concrete working period
- owner: Offshore
- key fields: start date, end date, installation, cycle, status, version lock
- tenant/site scope: yes
- relation to Builder: references assigned menu versions
- relation to Planera: feeds normalized input
- version semantics: yes
- required in MVP: yes
- persisted or derived: persisted

### OffshoreMealSlot
- purpose: one service slot in the period
- owner: Offshore
- key fields: date, meal, original projection fields, planned override fields, status
- tenant/site scope: yes
- relation to Builder: original menu projection
- relation to Planera: production input
- version semantics: yes
- required in MVP: yes
- persisted or derived: persisted or derived

### OffshorePortionOverride
- purpose: original versus adjusted portions
- owner: Offshore
- key fields: original count, adjusted count, scope, reason, audit metadata
- tenant/site scope: yes
- relation to Builder: none directly
- relation to Planera: input
- version semantics: yes
- required in MVP: yes
- persisted or derived: persisted

### OffshorePrepTemplate
- purpose: reusable prep knowledge
- owner: Offshore
- key fields: title, linked composition/component, timing, quantity, instructions
- tenant/site scope: yes
- relation to Builder: may reference composition/component
- relation to Planera: can later be suggested
- version semantics: optional
- required in MVP: yes
- persisted or derived: persisted

### OffshorePrepTask
- purpose: concrete prep item in a period
- owner: Offshore
- key fields: period, meal slot, template reference, status, source, audit metadata
- tenant/site scope: yes
- relation to Builder: may reference composition/component
- relation to Planera: may later be suggested
- version semantics: task version optional
- required in MVP: yes
- persisted or derived: persisted

### OffshoreFreezerTemplate
- purpose: reusable freezer knowledge
- owner: Offshore
- key fields: item name, timing, quantity, instructions
- tenant/site scope: yes
- relation to Builder: may reference composition/component
- relation to Planera: may later be suggested
- version semantics: optional
- required in MVP: yes
- persisted or derived: persisted

### OffshoreFreezerPull
- purpose: concrete freezer item in a period
- owner: Offshore
- key fields: period, meal slot, template reference, status, source, audit metadata
- tenant/site scope: yes
- relation to Builder: may reference composition/component
- relation to Planera: may later be suggested
- version semantics: task version optional
- required in MVP: yes
- persisted or derived: persisted

### OffshoreOrderReminder
- purpose: shared reminder to order or check something
- owner: Offshore
- key fields: title, deadline, linked meal or period, status, source, audit metadata
- tenant/site scope: yes
- relation to Builder: optional component reference
- relation to Planera: may later be suggested
- version semantics: optional
- required in MVP: yes
- persisted or derived: persisted

### OffshoreHandover
- purpose: period summary for the incoming cook
- owner: Offshore
- key fields: summary, open items, date, status, audit metadata
- tenant/site scope: yes
- relation to Builder: can reference original menus indirectly
- relation to Planera: can reference outputs later
- version semantics: yes
- required in MVP: yes
- persisted or derived: persisted

### OffshoreVirtualCook
- purpose: future staffing abstraction
- owner: Offshore
- key fields: name, validity range, notes
- tenant/site scope: yes
- relation to Builder: none
- relation to Planera: none directly
- version semantics: yes
- required in MVP: no
- persisted or derived: persisted later

### OffshoreCookAssignment
- purpose: link a period to a real or virtual cook
- owner: Offshore
- key fields: period, user or virtual cook, validity range, role
- tenant/site scope: yes
- relation to Builder: none
- relation to Planera: none directly
- version semantics: yes
- required in MVP: no
- persisted or derived: persisted later

## 23. MVP Scope

### Must be included in Offshore MVP
- Offshore foundation/app shell
- site and installation context
- settings skeleton
- four-week menu cycle
- Builder menu and version assignments
- Offshore period
- Friday dinner to Friday lunch service pattern
- Lunch/Kväll Period Planner grid
- period over two calendar weeks
- original menu projection
- actual planned override
- portion adjustments
- prep template and task
- freezer template and pull
- shared Husk att bestill
- handover
- history and copy previous period
- browser print
- tenant/site/RBAC hardening

### Must wait
- full crew portal
- full inventory
- supplier integration
- automatic purchasing
- advanced freezer optimization
- full AI planning
- advanced analytics
- PDF/DOCX export
- full offline support
- many rig or turnus templates
- advanced personnel scheduling
- automatic perfect prep generation
- full Planera production automation

## 24. Final Build Order
The first version should be built in this order.

### Ticket 1 - Foundation and app shell
Build:
- new separate Offshore module
- /offshore
- feature flag
- auth
- tenant/site context
- empty dashboard
- navigation
- settings skeleton
- separation from legacy Offshore

GZ:
`gz-offshore2-foundation-shell-v0`

### Ticket 2 - Installation settings and menu cycle domain
Build:
- installation and settings
- menu cycle
- menu cycle weeks
- rotation start
- rotation calculation
- Builder menu/version assignment contract

GZ:
`gz-offshore2-menu-cycle-v0`

### Ticket 3 - OffshorePeriod and service events
Build:
- period domain
- period states
- Friday dinner to Friday lunch generator
- meal slots and service events
- date/week metadata
- idempotent generation

GZ:
`gz-offshore2-period-domain-v0`

### Ticket 4 - Period Planner grid
Build:
- Lunch/Kväll grid
- route
- view model
- empty slots
- iPad-friendly baseline
- browser read-only state

GZ:
`gz-offshore2-period-planner-grid-v0`

### Ticket 5 - Menu cycle resolution per meal slot
Build:
- cross-week rotation resolution
- source menu week and index
- Builder menu and version pin per slot and period
- ISO year boundary tests

GZ:
`gz-offshore2-cycle-slot-resolution-v0`

### Ticket 6 - Builder/Menu Context projection
Build:
- original menu projection
- composition identity
- unresolved visibility
- no duplicated menu data
- safe fallback

GZ:
`gz-offshore2-builder-menu-projection-v0`

### Ticket 7 - Actual planned override
Build:
- planned composition
- planned text
- deviation note
- changed metadata
- original menu remains immutable
- changed indicator in grid

GZ:
`gz-offshore2-planned-menu-override-v0`

### Ticket 8 - Portion overrides
Build:
- installation default
- period override
- meal slot override
- original and adjusted values
- view integration

GZ:
`gz-offshore2-portion-overrides-v0`

### Ticket 9 - Prep templates and tasks
Build:
- template
- period task
- instantiate
- copy
- status
- component and composition links

GZ:
`gz-offshore2-prep-workflow-v0`

### Ticket 10 - Freezer templates and pulls
Build:
- freezer template
- period pull
- status
- copy and reuse
- meal slot linkage

GZ:
`gz-offshore2-freezer-workflow-v0`

### Ticket 11 - Shared Husk att bestill
Build:
- site-shared reminders
- open/done/cancelled
- dashboard summary
- optional period, slot, and component links

GZ:
`gz-offshore2-order-reminders-v0`

### Ticket 12 - Handover and period history
Build:
- handover
- completed period
- historical read-only view
- copy previous period to new draft

GZ:
`gz-offshore2-handover-history-v0`

### Ticket 13 - Print and MVP hardening
Build:
- browser print
- permissions
- tenant/site integrity
- empty and error states
- accessibility
- responsive iPad polish
- full regression

GZ:
`gz-offshore2-mvp-hardening-v0`

### Ticket 14 - Planera 2.0 adapter skeleton
Build only when the operational period works:
- normalized input
- contract mapping
- safe recommendations
- no automatic writes
- manual fallback preserved

GZ:
`gz-offshore2-planera-adapter-v0`

## 25. First Implementation Ticket
The next code ticket after this blueprint is the Offshore foundation and app shell.

### It should build only
- new module structure
- feature flag
- /offshore
- auth and RBAC
- tenant/site context
- professional empty dashboard
- navigation
- empty active-period state
- settings skeleton
- separation from legacy Offshore
- tests

### It should not build
- database period models
- menu cycle
- Builder integration
- Planera adapter
- prep
- freezer
- reminders
- handover

## 26. Documentation Structure
Update:
- docs/offshore2/current_state_and_first_slice.md
- docs/offshore2/product_blueprint.md
- docs/offshore2/README.md

### current_state_and_first_slice.md
Technical inventory:
- what exists
- what is missing
- active versus legacy
- technical start points

### product_blueprint.md
The decided product:
- user flow
- MVP
- architecture
- domain proposals
- wireframes
- ticket order
- definition of done

### README.md
Should contain:
- document navigation
- status
- which file is authoritative for product decisions
- which file is authoritative for current state

It should clearly say:
Yuplan Offshore 2.0 is not implemented yet. These documents describe the module that will be built.

## 27. Comparison to Current Docs
Current documentation must be corrected so that it explicitly matches the locked MVP.

### Already aligned
- Offshore is not implemented yet.
- Old prototype is reference material, not the new architecture.
- Builder owns canonical menu identity.
- Planera 2.0 is a generic production engine.
- Docs-only scope is correct.

### Must be corrected or tightened
- grid must be primary, not just a day-by-day document
- period must be Friday dinner to Friday lunch
- period must cross two calendar weeks
- original menu and planned output must be separated
- menu version locking must be explicit
- prep template and prep task must be separate
- freezer template and freezer pull must be separate
- Husk att bestill must be shared site workflow
- virtual cooks must be explicitly decided as future scope
- Menu Context must be described as a technical start point, not a full domain if persistence and ownership are not real yet
- Planera timing must be future-compatible, not a blocker
- ticket order must start with foundation/app shell

## 28. Wireframes
The blueprint should include text wireframes for:
1. Offshore empty dashboard
2. Active dashboard
3. Menu cycle settings
4. Period Planner grid
5. Meal slot detail
6. Prep workspace
7. Freezer workspace
8. Husk att bestill
9. Handover
10. Print view

### Empty dashboard
```text
┌──────────────────────────────────────────────┐
│ Offshore – Installation X                   │
├──────────────────────────────────────────────┤
│ No active period                             │
│ Start by creating an installation context    │
│ and a menu cycle.                            │
└──────────────────────────────────────────────┘
```

### Active dashboard
```text
┌──────────────────────────────────────────────┐
│ Offshore – Installation X     Period active  │
├──────────────────────────────────────────────┤
│ Today: Tuesday                               │
│ Lunch: ...                                   │
│ Dinner: ...                                  │
├───────────────────┬──────────────────────────┤
│ Prep today        │ Freezer pulls            │
│ □ ...             │ □ ...                    │
├───────────────────┴──────────────────────────┤
│ Handover / reminders                         │
└──────────────────────────────────────────────┘
```

### Menu cycle settings
```text
┌──────────────────────────────────────────────┐
│ Menu cycle                                   │
├────────┬──────────────┬──────────────────────┤
│ Week 1 │ Builder A    │ locked              │
│ Week 2 │ Builder B    │ editable            │
│ Week 3 │ Builder C    │ locked              │
│ Week 4 │ Builder D    │ editable            │
└────────┴──────────────┴──────────────────────┘
```

### Period Planner grid
```text
┌──────────────────────────────────────────────────────────────┐
│ Friday dinner → Thursday dinner → Friday lunch / handover   │
├────────────┬──────────────────────┬─────────────────────────┤
│ Day        │ Lunch                │ Kväll                   │
├────────────┼──────────────────────┼─────────────────────────┤
│ Friday     │ -                    │ ...                     │
│ Saturday   │ ...                  │ ...                     │
│ Sunday     │ ...                  │ ...                     │
│ Monday     │ ...                  │ ...                     │
│ Tuesday    │ ...                  │ ...                     │
│ Wednesday  │ ...                  │ ...                     │
│ Thursday   │ ...                  │ ...                     │
│ Friday     │ handover lunch       │ -                       │
└────────────┴──────────────────────┴─────────────────────────┘
```

## 29. Security
Binding rules:
- tenant isolation
- site isolation
- role checks
- no cross-site Builder menus
- no leaked IDs from other tenants
- period belongs to current installation
- menu cycle belongs to current installation
- templates can only be tenant-global or site-local through explicit scope
- all write actions are audited
- completed periods are read-only unless explicitly reopened by an authorized role

## 30. Scope
Only documentation may change.

Allowed files:
- docs/offshore2/current_state_and_first_slice.md
- docs/offshore2/product_blueprint.md
- docs/offshore2/README.md

No production code.

No models.
No migrations.
No templates.
No routes.
No feature flags.
No API changes.
No tests for unimplemented features.

## 31. Tests and Baseline
Run existing tests relevant to the current platform baseline:
- Planera v2
- Builder Menu Context
- Turnus
- Builder menu projection/context

Then run the full suite:

```text
pytest -q
```

Report:
- passed
- failed
- skipped
- warnings

## 32. Scope Control
Run:

```text
git status --short
git diff --stat
git diff --name-status
```

Expected result:
- only docs/offshore2/*

## Definition of Done
This ticket is done when:
- the new Offshore is explicitly described as not yet implemented
- the old Rigplan prototype is a requirement source, not the codebase
- Friday dinner to Friday lunch is documented
- Lunch/Kväll grid is the central MVP view
- the period can cross two calendar weeks
- four-week menu cycle is defined
- Builder menu and version locking is defined
- original menu and actual plan are separated
- prep template and task are defined
- freezer template and pull are defined
- shared Husk att bestill is defined
- handover is defined
- history and copy-forward are defined
- Menu Context has a realistic role
- Planera is the future engine but does not block MVP
- virtual cooks have an explicit decision
- MVP scope is locked
- ticket sequence is locked
- first implementation ticket is foundation/app shell
- only documentation has changed

## Decision
READY FOR GZ

Föreslagen GZ:
gz-offshore2-product-blueprint-v0