# Veckovy v1 — Kitchen Week Overview (All Departments)

Canonical weekview used by kitchen staff. Read-only residents and diet defaults; allows marking specialkost per cell. No UI redesign; aligned with existing service/API.

## Route
- GET `/ui/weekview?site_id={site}&year={yy}&week={ww}`
- When `department_id` is empty or missing, renders all-departments grid for the active site.
- Site-lock: for site-bound admins (`session.site_lock == true`), the effective site is the bound session site. Site switching links are suppressed.

## Template
- `templates/ui/weekview_all.html`
- Displays per-department cards with a week table.

### Columns
- Days Mon–Sun as headers, each with two subcolumns:
  - Lunch
  - Kväll (Dinner)

### Rows
- First row: `Boende` shows effective resident count per day/meal.
- Diet rows: one per specialkost type determined by the union rule:
  - Any department diet default with `default_count > 0`.
  - Plus any diet type that has a mark anywhere in the week (Lunch or Dinner) even if its default is 0 or absent.

## Data Model (per day)
- `residents`: `{ lunch: int, dinner: int }` derived by precedence:
  1. Per-day schedules for the specific week.
  2. Forever per-day schedules.
  3. Weekly override (same-for-week legacy).
  4. Department `resident_count_fixed` fallback.
  - Optional explicit per-day counts in weekview repo override the above.
- `diets`:
  - `lunch`: list of `{ diet_type_id, resident_count, marked }` entries.
  - `dinner`: same structure.
  - Resident_count equals department default count for the diet type (0 if absent), but presence follows the union rule above.
- `alt2_lunch`: boolean flag for Alt2 availability.
- `menu_texts`: optional enrichment with `alt1`, `alt2`, `dessert` for lunch and `alt1/alt2` for dinner.

## Click Semantics
- Only specialkost cells are clickable to toggle `marked`.
- Optimistic UI: immediately adds/removes `.marked` class.
- POST `/api/weekview/specialdiets/mark` with JSON payload:
  - `{ year, week, department_id, meal, weekday_abbr, diet_type_id, marked }`
  - Requires `If-Match` header with current ETag.
- On `200 OK`: update section `data-etag` with the returned ETag.
- On `412 Precondition Failed`: fetch latest ETag via `GET /api/weekview/etag?department_id={id}&year={yy}&week={ww}` and retry once; revert optimistic change if still failing.

## ETag Retry
- Each department card section carries `data-etag` from `WeekviewService.fetch_weekview()`.
- JS toggles use ETag; fallback path fetches latest and retries once.

## Site-lock
- When `session.site_lock` is true, the UI hides site-switch links and uses the bound `session.site_id` regardless of querystring.

## Scope
- Week-scoped across `{year, week, department_id}` for marks, residents overrides, and alt2 flags.
- No UI redesign, no backend refactors beyond union rule support.

## Testing Requirements
- GET `/ui/weekview` renders all-departments grid with current week when `department_id` is empty.
- "Boende" row exists.
- Diet rows render for defaults `> 0`.
- Diet cells include required `data-*` attributes and the enclosing section has `data-etag`.
- Site-lock suppresses site-switch UI.
- Union regression: a diet type not in defaults (or with default 0) but with a mark anywhere in the week renders a row and cells.
