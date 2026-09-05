# Planera 2.0 — Production Needs V1

**Status:** Planned Planera 2.0 development  
**Priority:** After current test-baseline cleanup and Planera 2.0 Kommun acceptance  
**Scope:** Keep the first version deliberately simple  

## Purpose

Planera 2.0 should automatically use information Yuplan already has to calculate what raw materials should be available for upcoming production.

The first version should **not** become an inventory, thawing, purchasing, shelf-life or advanced prep system.

The core idea is:

**Published menu + actual selected dishes / portions + Builder recipe quantities = production raw-material need**

For Kommun, Planera should be able to use:

- the published menu
- which menu option each department has selected
- resident / portion totals
- canonical requirements where relevant
- structured Dishes / Compositions from Builder
- recipe / ingredient quantities per portion

From this, Yuplan can automatically present a simple weekly indication of how much of important raw materials the kitchen should have available in order to deliver the planned production.

---

## Example

Published Wednesday menu:

**Fish dish — 137 portions**

Builder recipe data:

- saithe: 140 g / portion
- potatoes: 180 g / portion
- sauce: 90 g / portion

Planera can calculate:

- saithe: 19.18 kg
- potatoes: 24.66 kg
- sauce: 12.33 kg

The useful user-facing result can simply be something like:

> Wednesday — Fish — 137 portions  
> Approx. 19.2 kg saithe required for production

Or, at week level:

- saithe — 19.2 kg
- minced beef — 28.4 kg
- falukorv — 31 kg
- chicken — 22 kg

The purpose is not to tell the kitchen **how** to source or store the product. The purpose is to tell the kitchen **what quantity should be available for planned production**.

---

## V1 principle

If Yuplan already knows the information, the user should not have to enter it again.

The calculation should therefore be automatic and derived from canonical data.

Basic formula:

**planned portions × recipe quantity per portion = raw-material production need**

This can then be aggregated by:

- service date
- dish
- component / ingredient
- week
- installation / site where relevant

---

## User experience

The result does not necessarily need to live inside the main Planera workspace.

Possible surfaces to evaluate later:

- dashboard card / link
- "Upcoming production needs"
- "Next week's raw-material needs"
- weekly preparation / production overview
- dedicated read-only production-needs view

The final UX location must be decided during the future Planera UX design phase.

The important architecture principle is that Planera generates the result automatically; the UI only chooses the best way to surface it.

---

## Prep suggestions

Prep suggestions are **not required for V1**.

A later simple extension could allow Builder to store minimal optional information such as:

- prep instruction
- number of days before service

Example:

- "Portion fish" — 1 day before service
- "Roll meatballs" — 1 day before service

Planera could then turn structured menu and production quantities into simple reminders.

However, this must remain a later extension and must not block the first raw-material-needs version.

---

## Explicitly out of scope for V1

Do **not** build these into the first version:

- stock balance
- frozen vs fresh state
- thawing calculations
- shelf life
- FIFO
- automatic purchasing
- supplier lead times
- delivery scheduling
- automatic inventory reservation
- advanced prep dependency graphs
- AI optimisation
- warehouse / freezer location tracking

These can be future layers if real users prove the need.

---

## Architecture direction

This feature should sit above the same generic Planera 2.0 production-demand model, not inside Kommun-specific core logic.

Conceptual flow:

**Builder food knowledge**  
Components / Dishes / Recipes / Menus

↓

**Published / effective menu**

+

**Business demand context**  
For Kommun: department choices, residents, requirements, overrides

↓

**Planera 2.0 production demand**

↓

**Production Needs projection**  
What raw materials / components are needed and in what quantities?

↓

**Operational surfaces**  
Dashboard / weekly overview / future prep reminders

This keeps the same concept reusable later for Offshore, Hotel/Banquet and other applications.

---

## Product principle

The first version should feel useful because it is simple:

> "Based on next week's published menu and current selections, this is roughly what the kitchen needs to have available for production."

That alone is valuable.

Do not over-engineer the first version into a complete inventory or production-management system.

---

## Future decision points

Before implementation, define:

1. Which recipe level is canonical for quantity calculation: ingredient, component or recipe line.
2. Which raw materials should be surfaced by default so pantry items such as salt, water and pepper do not dominate the view.
3. How menu choices and canonical requirement groups affect dish-specific quantities.
4. How unresolved / partially structured Builder dishes are represented.
5. Whether totals are shown by day, by week, or both.
6. Whether the first UI surface belongs on the dashboard or inside Planera.
7. How much rounding is appropriate for kitchen use.

These decisions should be made during Planera acceptance / UX design, before implementation.
