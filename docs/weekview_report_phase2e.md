# Weekview Report – Phase 2.E (Design & Skeleton)

Status: Design-only (no real aggregation yet). Implementation of logic deferred to Phase 2.E.1.

## a) Scope
"Weekview Report" is a read-only weekly summary per site derived from Weekview outcome data. It allows filtering by:
- Site (required)
- Week & Year (required)
- Department scope:
  - Single department (department_id provided), or
  - ALL departments at the site (department_id omitted)

No editing or mutations in this phase. Focus: consistent, stable aggregation contract and iPad-friendly presentation.

## b) Data Sources
Single source of truth: existing Weekview data (via `WeekviewService`/repo stack) which already exposes:
- Residents per day/meal (`residents_counts` → enriched per-day `residents.lunch` / `residents.dinner`)
- Special diets per day/meal with `resident_count` (default count) and `marked` flag
- Alt2 lunch flags (context only; not a direct metric)

No dedicated report tables. Report is a computed projection over Weekview-compatible structures. Avoids divergence and duplication.

## c) Aggregation Rules (to be implemented in Phase 2.E.1)
For each (site, year, week):
1. Department resolution:
   - If `department_id` given → exactly that department.
   - Else → all departments for the site ordered by name.
2. For each department and each meal (`lunch`, `dinner`):
   - `special_diets[diet_type].count` = sum over all 7 days of `resident_count` where `marked == True` for that diet & meal.
   - `residents_total` = sum of resident counts across all days for that meal.
   - `normal_diet_count` = max(0, `residents_total - sum(special_diets[*].count`).
3. Include only diet types with non-zero `count` in `special_diets` array.
4. Marked semantics:
   - A diet entry contributes its `resident_count` only if `marked == True` for that day+meal.
   - Unmarked entries are treated as zero contribution for that day.
5. Normal diet definition:
   - "Guests without a special diet outcome for that meal across the week." (Derived; not directly stored.)

Edge Handling (documented for Phase 2.E.1 implementation):
- Missing resident counts for a day → treat as 0 (and optionally track a warning set).
- Negative intermediate values → clamp to 0 (defensive).

## d) API Shape (Proposed)
`GET /api/reports/weekview`

Query Params:
- `site_id` (string, required)
- `year` (int, required; 2000 ≤ year ≤ 2100)
- `week` (int, required; 1 ≤ week ≤ 53)
- `department_id` (string, optional)

Response (Phase 2.E.1 goal):
```json
{
  "site_id": "...",
  "site_name": "...",
  "year": 2025,
  "week": 11,
  "meal_labels": { "lunch": "Lunch", "dinner": "Kvällsmat" },
  "departments": [
    {
      "department_id": "...",
      "department_name": "Avd 1",
      "meals": {
        "lunch": {
          "residents_total": 42,
          "special_diets": [
            {"diet_type_id": "gluten", "diet_name": "Gluten", "count": 8},
            {"diet_type_id": "laktos", "diet_name": "Laktos", "count": 3}
          ],
          "normal_diet_count": 31
        },
        "dinner": {
          "residents_total": 40,
          "special_diets": [],
          "normal_diet_count": 40
        }
      }
    }
  ]
}
```

Phase 2.E (this PR) returns placeholder values with the same top-level keys; counts default to 0; `special_diets` empty.

Notes:
- Read-only; no caching layer initially beyond standard Flask stack.
- Feature flag can piggyback `ff.weekview.enabled` or a dedicated `ff.weekview.report.enabled` later.

## e) UI View (Skeleton Now, Full Later)
Route: `/ui/reports/weekview?site_id=...&year=YYYY&week=WW[&department_id=...]`

Header: `Statistik – vecka {week} – {site_name}` (+ department name if single).

Filters (planned, not fully implemented yet):
- Prev/Next week links.
- Department selector: dropdown with "Alla avdelningar" when `department_id` omitted.

Layout (Phase 2.E.1 target):
- For each department: Card or compact table.
  - Department name.
  - Meal sections (Lunch / Kvällsmat):
    - Row: `Boende totalt: X`
    - List of special diets (diet name: count) sorted by descending count.
    - Row: `Normalkost: Y`.

Skeleton (this PR):
- Header only.
- Simple JSON debug dump of placeholder response.
- "Coming soon" message.

## f) Error & Edge Cases
- Site not found → 404 `{error: "not_found", message: "Site not found"}`.
- Invalid year/week → 400 `{error: "bad_request"}`.
- No departments (ALL scope) → return empty `departments: []` and show message `Ingen statistik tillgänglig för vecka {week}.` in UI.
- Partial Weekview data (future) → may attach `warnings: [ ... ]` at top-level (Phase 2.E.1 consideration).

## g) Future Extensions (Out of Scope Now)
- Date range (multi-week) reports.
- CSV / PDF export.
- Per-day drilldown links back to `/ui/weekview`.
- Localization for meal labels and diet names (sv-SE, nb-NO, etc.).
- Tenant-level caching & concurrency optimization.

## h) Implementation Plan Split
Phase 2.E (This PR):
- Docs + skeleton API/UI + basic tests.

Phase 2.E.1:
- Implement real aggregation logic using `WeekviewService.fetch_weekview` for each department.
- Unit tests verifying diet totals, normal diet computation, and multi-department correctness.
- UI rendering of meal cards.

Phase 2.E.2 (potential):
- Export features, localization refinements, warnings surface.

## i) Placeholder Contract (Skeleton)
Skeleton response must contain keys: `site_id, site_name, year, week, meal_labels, departments`.
Each department object contains: `department_id, department_name, meals.lunch, meals.dinner` each with: `residents_total, special_diets (array), normal_diet_count`.
All numeric counts = 0; arrays empty.

## j) Non-Goals for Phase 2.E
- No mutation endpoints.
- No caching layer optimization.
- No aggregation across multiple weeks.
- No custom diet name mapping beyond raw IDs (will mirror existing Weekview).

## k) Security & Authorization
- Same role gating as Weekview read: viewer/admin/superuser/cook/unit_portal (SAFE_UI_ROLES).
- CSRF not required (GET only).

## l) Testing Strategy (Skeleton)
- API: `GET /api/reports/weekview` returns 200 with correct keys.
- UI: `GET /ui/reports/weekview` returns 200 and contains header + placeholder marker.

## m) TODO Markers in Code
Add `# TODO Phase 2.E.1: implement aggregation per week according to docs/weekview_report_phase2e.md` in API handler and UI route.

---
Design prepared for implementation. See `docs/weekview_unified_proposal.md` for original Weekview context.
