# Menu v1 — Backend Contract for Weekview

Minimal structure to serve per-day menu data (Lunch/Dinner) used by weekview.

## Data Contract
- Scope: (`site_id`, `year`, `week`, `day` 1..7)
- Meals: `lunch`, `dinner`
- Fields per meal:
  - `alt1_text` (string | null)
  - `alt2_text` (string | null)
  - `dessert` (string | null; optional; lunch only)

## Repo API
- `get_menu_week(site_id, year, week) -> { days: { mon|tue|wed|thu|fri|sat|sun: { lunch: {alt1, alt2, dessert}, dinner: {alt1, alt2} } } }`
- `get_menu_day(site_id, year, week, day) -> { lunch: {alt1, alt2, dessert}, dinner: {alt1, alt2} }`
- `upsert_menu_item(site_id, year, week, day, meal, alt1_text, alt2_text, dessert)` — test-only seed helper.

## Endpoint
- `GET /api/menu/day?year={yy}&week={ww}&day={d}`
  - `site_id` resolved from session (`session.site_id`), respecting site-lock.
  - Returns JSON `{ lunch: {...}, dinner: {...} }`.

## Notes
- No UI import; tests programmatically seed via repo.
- SQLite-first schema creation for tests; production assumes migration.
