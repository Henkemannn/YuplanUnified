# Weekview Site Overview (Kommun) — Design (Docs Only)

Context
- We have a department-level Weekview UI: `GET /ui/weekview?site_id=...&department_id=...&year=YYYY&week=WW`.
- It shows lunch/dinner texts (alt1/alt2 + dessert), Alt2 lunch highlight, and residents per day.
- Goal now: design a site-level overview (one site, one week, all departments in a single read-only view) similar to the legacy Varberg main Weekview.

Scope (Phase 1 — read-only)
- One row per department for the selected site and week.
- Columns: department name, weekly/aggregate resident counts, and a 7-day strip (Mon–Sun) with: a menu icon per day and an Alt2 indicator specific to that department/day (lunch).
- Read-only in Phase 1 (no editing/marking yet). Menu icon opens a small popup with that day’s site-level menu (lunch/dinner/dessert).

Proposed Route (UI)
- `GET /ui/weekview_overview?site_id=<uuid>&year=YYYY&week=WW`
  - Params validation: `year` in [2000..2100], `week` in [1..53], `site_id` must exist.
  - Auth: same roles as the current Weekview UI (superuser, admin, cook, unit_portal).

Data Needed (per department row)
- `department_name` (string)
- Residents aggregation (Phase 1):
  - Option A (simple): total `residents_lunch_week` and `residents_dinner_week` (sum across days).
  - Option B (richer, optional): 7 daily counts for quick glance (L/M per day). Phase 1 can start with Option A and add Option B if easy.
- Per-day strip (Mon..Sun):
  - `has_menu_icon` (bool) — show menu icon button if any menu texts exist for that day (lunch or dinner).
  - `alt2_lunch` (bool) — highlight flag per department/day when Alt2 is selected for lunch.
- Placeholders (future phases):
  - Special diet counts per department/day (e.g., Gluten, Laktos, Timbal).
  - “Done” marks per department/day/meal that tie into reporting.

Per-Day Behavior
- Menu popup: clicking the day’s icon opens a small overlay summarizing that day’s site-level menu: lunch alt1/alt2 (+ dessert), dinner alt1/alt2 (when present).
- Alt2 status: show a subtle yellow badge/dot if `alt2_lunch == true` for that department/day (leverages existing semantics from Weekview service).

UX Notes
- Table-like overview (iPad-friendly):
  - Left: Department name (sticky/fixed column if feasible).
  - Next: weekly residents summary (Lunch/Dinner totals).
  - Right: 7 compact day cells (Mon..Sun) with:
    - Menu icon when menu exists
    - Alt2 visual state for lunch (e.g., a small square/indicator with yellow background)
- Readability: minimal borders, consistent padding, large-enough touch targets for the icons.
- Print: future enhancement; Phase 1 can deprioritize print CSS.

Phase Plan
- Phase 1 — Read-only overview:
  - UI: one screen for the site showing all departments with per-day menu icon and Alt2 markers; residents shown as weekly totals.
  - No interactions except opening a non-editing menu popup.
- Phase 2 — Special diets & progress:
  - Show per-department/day special diet counts summary (read-only).
  - Optionally show a small “done” counter if it’s e.g., reported/confirmed (integration to be designed).
- Phase 3 — Interactions:
  - Add inline interactions (mark done per department/day/meal) with ETag/If-Match-safe updates.
  - Wire into reporting/export flows.

Data Sources & API (Docs Only; no changes in this PR)
- Reuse the enriched Weekview service output already available per department (`GET /api/weekview`).
- Phase 1 UI can obtain overview data via one of two strategies:
  1) Simple N calls: loop departments for the site and call the existing `GET /api/weekview` per department, aggregating results into the view model. (Acceptable in early phase and small/medium sites.)
  2) Later optimization: add a site-scoped aggregator endpoint (e.g., `/api/weekview/site-overview`) that returns a compact array of department rows with per-day `has_menu` and `alt2_lunch` flags and residents rollups. Not implemented now; only a potential evolution.
- Menu popup content can reuse the same menu texts already present in each department’s `days[].menu_texts` (site-level menu is the same across departments unless overridden). For Phase 1, showing the menu from the first department with data is acceptable; later, a dedicated site-level menu fetch could be introduced.

View Model (Sketch)
```
WeekviewOverviewVM(
  site_name: str,
  year: int,
  week: int,
  departments: list[DepartmentRowVM]
)

DepartmentRowVM(
  department_id: str,
  department_name: str,
  residents_lunch_week: int,
  residents_dinner_week: int,
  days: list[DeptDayVM]  # 7 items (Mon..Sun)
)

DeptDayVM(
  has_menu_icon: bool,
  alt2_lunch: bool,
  # optional (Phase 2+): special diet counts summary
)
```

Acceptance Criteria (Phase 1 — Read-only)
- Route `/ui/weekview_overview` renders 200 for valid inputs; 400 for invalid week/year; 404 if site not found.
- For a seeded site with two departments:
  - Department rows render with names and weekly residents totals.
  - Day cells show menu icon where at least one menu text exists and show Alt2 indicator when Alt2 lunch is selected for that dept/day.
  - No editing controls are present; clicking menu icons opens a read-only popup.
- The page is legible and touch-friendly on iPad.

Constraints
- This deliverable is documentation only; do not modify code or APIs in this PR.
- Prefer reusing the existing Weekview service; do not propose new contracts beyond a future optional aggregator.

Open Questions / Assumptions
- For Phase 1, are weekly residents totals sufficient, or do we need per-day counts in the overview? (Proposed: weekly totals first, upgrade to per-day later.)
- Menu popup content source for a site: unify on a primary/first-available department’s menu texts, unless site-level overrides exist.
- Department ordering: alphabetical vs. custom order from site config (out of scope for Phase 1).
