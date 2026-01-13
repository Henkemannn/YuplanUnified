Scope

Adds unified meal/day details UI on top of /ui/planera/day?ui=unified.

Phase 1: Header + cards for Meny, Specialkost & antal, Registreringar, Alt 2.

Phase 2: Read-only placeholders for future modules: Prepp, Inköp, Frys, Recept.

UI

New template unified_planera_day.html using unified layout and design tokens.

Shows date, weekday, meal (Lunch/Kvällsmat), department and site.

Displays menu text, diet badges, registration status and Alt 2 badge when available.

Adds four future cards with “Kommer senare…” text for prep/purchases/freezer/recipes.

Docs

docs/planera_day_unified.md – describes the unified meal/day details view and its sections.

Linked from README.md.

Design

docs/menu_component_design.md – early design notes for a future MenuComponent / menydetalj-ID used by prep/inköp/frys/recept.

ui_blueprint.py annotated with TODOs where component_id should be exposed in vms later.

Tests

tests/ui/test_unified_planera_day_phase1.py – happy path and empty menu behavior.

tests/ui/test_unified_planera_day_phase2.py – asserts Prepp/Inköp/Frys/Recept cards and placeholders.

No schema changes, no new backend services; this is UI-only on top of the existing /ui/planera/day vm.
