Title: P0 Planering – Tillagningslista + bulkmarkera specialkost

Summary
- Primarily shifts Planering to a print-ready “Tillagningslista” worklist with clear Normalkost and Specialkost chips.
- Adds a safe bulk action to mark produced special diets in weekview across all site departments.
- Maintains CSP: no inline scripts; all interactions are via external JS.

Scope of Changes
- UI: templates/ui/kitchen_planering_v1.html – adds “Arbetskort” section with chips and a large print button; consistent menu line with /menu/week as single source.
- JS: static/ui/kitchen_planering_v1.js – initializes bulk mark action and special chips; keeps mode persistence and print handlers.
- CSS: static/unified_ui.css + static/css/kitchen_planering_print.css – responsive two-column workcards, chip styles, and print-only output.
- API: core/ui_blueprint.py – site-scoped POST /api/planering/mark_produced_special for marking; imports fixed. Also clear endpoint in core/planera_api.py.

Behavior
- “Markera producerat i veckovyn” posts {site_id, year, week, day_index, meal, optional diet_type_ids} and writes weekview_registrations marks for diets with count > 0 in each department.
- Button is present only when specials exist; disabled when none.
- Menu header comes from /menu/week; neutral title suggestion for normal lunch.

Security
- CSP-safe: no inline JS; uses defer external scripts; CSRF headers included.

Tests
- tests/ui/test_kitchen_planering_bulk_mark_weekview.py – verifies endpoint marks weekview registrations.
- tests/ui/test_kitchen_planering_special_chips_present.py – asserts bulk button text and chip markup presence.
- Broader suite: `pytest -k kitchen_planering` → 21 passed, 2 skipped.

Notes
- This PR is not final acceptance; Specialkost planering UX will iterate to better match “tillagningslista” model.
