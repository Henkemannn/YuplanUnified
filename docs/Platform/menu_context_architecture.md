Menu Context Architecture
🎯 Purpose

This document defines how Yuplan should handle menus and menu-like structures without locking the system to a classic weekly lunch menu model.

The goal is to support:

weekly municipal menus
catering proposals
à la carte menus
event menus
draft/freeform menus
component lists
composition lists

without forcing everything into:

week
day
meal slot
🧠 Core Principle

A menu is not inherently a weekly schedule.
A menu is a structured collection of rows within a context.

This is critical.

Yuplan must not assume that all menus are:

Monday–Sunday
lunch/dinner/dessert
weekly recurring

That is only one context.

🔑 Main Separation
1. Library Layer

This is where users work freely with reusable building blocks:

components
compositions
recipes
menu drafts/templates

No day/week/meal binding is required here.

Examples:

build a new dish
create a catering suggestion
prepare an à la carte structure
maintain a reusable dish library
2. Planning Context Layer

This is where a menu or menu row is placed into an operational context.

Examples:

week 16, Monday lunch
bankett event on 2026-05-19
offshore day shift
catering proposal for a client
site-specific draft menu

This layer adds scheduling/serving context.

🧱 Menu as Contextual Container

A menu should be treated as a container with metadata describing its context.

Suggested Menu fields
menu_id
tenant_id
site_id (nullable)
title
context_type
status
version
created_at
updated_at

Optional context-related fields depending on type:

week_key (nullable)
event_id (nullable)
service_date (nullable)
notes (nullable)
🧭 Context Types

Suggested first-level context types:

weekly
event
a_la_carte
proposal
freeform
library_draft

These should guide UI and validation, but not hard-lock the core model too early.

🧾 Menu Row Principle

A menu row should represent a structured item in a menu context.

A row may point to:

a composition
unresolved text

Later it may also support:

component-only references
recipe-level references
event-course references

But the key principle remains:

A row belongs to a menu context, not necessarily to a weekday meal grid.

🧱 Context-Specific Row Metadata

Different menu contexts may require different metadata.

Weekly context

May use:

day
meal_slot
Event context

May use:

course
segment
service_time
À la carte

May use:

section
category
sort_order
Proposal/freeform

May use:

heading
grouping label
notes

Therefore:

day
meal_slot

must not be treated as universal truth.

They are only valid for some menu types.

🚫 What Must Be Avoided

Yuplan must not assume:

every menu has weekdays
every menu has lunch/dinner
every row belongs to a week plan
every dish is imported via municipal schedule logic

That would make the platform too narrow again.

✅ What Must Be Supported

Yuplan must support these use cases side by side:

Weekly municipal use
Monday lunch
Tuesday dinner
dessert
Catering
starter
main
dessert
coffee add-on
À la carte
starters
mains
desserts
sides
Event / bankett
courses
guest segments
service points
Free drafting
build dishes without assigning them yet
🔗 Relationship to Builder

This means the Builder should not be treated as:

a weekly menu builder only

It should be treated as:

component builder
composition builder
menu builder
library builder

And then later:

context-aware planning builder
🔗 Relationship to Planera 2.0

Planera 2.0 should consume context-bound menu data when needed, but not define the global truth of what a menu is.

Correct model:

Library layer defines reusable structures
Menu context layer places them into operational use
Planera consumes the relevant planning context

This keeps the engine generic and reusable.

🖥 UI Implications

The UI should later allow at least two clear modes:

1. Build freely
create dish
create composition
create menu draft
no schedule required
2. Assign context
place dish/menu into:
weekly plan
event
proposal
à la carte structure

This separation will make Yuplan much more powerful and much less narrow.

🧠 Strategic Importance

This architecture protects Yuplan from becoming “just a weekly lunch menu system”.

It keeps the platform open for:

municipality
offshore
catering
hotel
bankett
à la carte
storkök

This is one of the key design decisions that keeps Yuplan broad enough to become a real platform.

🚀 Recommended Implementation Order
Phase 1

Keep current weekly-style builder working.

Phase 2

Add free composition/dish creation independent of menu schedule.

Phase 3

Introduce menu context typing:

weekly
proposal
freeform
event
à la carte
Phase 4

Refactor row metadata so day/meal_slot become context-specific rather than universal.

✅ Summary
A menu is a structured collection of rows in a context
Week/day/meal are not universal truths
Yuplan must support both free creation and contextual planning
Library and planning context must remain separate
This is necessary to avoid becoming too narrow again