# Weekview UI Phase 1 — Read-only

Summary
- Adds a server-rendered Weekview (Kommun) page backed by the enriched API.
- Route: `GET /ui/weekview?site_id=...&department_id=...&year=YYYY&week=WW`
- Read-only: menu texts (lunch/dinner + dessert), Alt2 lunch highlight, residents per day.

Changes
- core/ui_blueprint.py
  - New `GET /ui/weekview` endpoint (auth roles: superuser, admin, cook, unit_portal).
  - Validates `year` (2000–2100) and `week` (1–53), resolves `site_name` and `department_name` via DB, then calls `WeekviewService` to fetch the enriched payload.
  - Builds a clean view model: `{site_name, department_name, year, week, has_dinner, days[]}` where each day maps `date`, `weekday_name`, `lunch_alt1|alt2|dessert`, `dinner_alt1|alt2`, `alt2_lunch`, `residents_lunch|residents_dinner`.
  - `has_dinner` computed as any dinner text present across the week; template uses it to conditionally show dinner columns.
- templates/ui/weekview.html
  - Header: `Vecka {{ week }} – {{ department_name }}, {{ site_name }}`.
  - Mon–Sun table with Lunch Alt1/Alt2 (+ Dessert), optional Dinner columns when present, residents shown in a compact style. `.alt2-gul` class marks lunch Alt2 when `alt2_lunch` is true.
  - Minimal, scoped CSS for readability on iPad.
  - Prev/next week navigation via simple links that adjust query parameters.
- tests/ui/test_weekview_ui_phase1.py
  - Seeds a site + department and a week with:
    - Monday lunch alt1/alt2/dessert
    - Tuesday dinner alt1
    - Alt2 flag for Monday
    - Residents for Monday lunch and Tuesday dinner
  - Asserts:
    - Header contains week/site/department
    - Menu texts present
    - `.alt2-gul` appears
    - Dinner columns present when dinner is seeded
  - Bonus test: week without dinner → dinner columns hidden

Notes
- This PR is strictly read-only (no clicks, no changes). It consumes the enriched `GET /api/weekview` service output; Phase 2 will add interactions (marks, Alt2 toggling, residents editing) with ETag handling.
- Error handling: responds 400 on invalid week/year, 404 when site/department not found.

Follow-ups
- Small UI polish (Phase 1.1) based on feedback.
- Phase 2: interactions + ETag/If-Match flows.
