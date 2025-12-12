# Weekly Reports – Current Behaviour Inventory

This document summarizes how weekly reporting currently works without changing behaviour. It covers routes, templates, services, and data sources involved in the two report flows: Weekview Report (menu/meal counts per department/day) and Weekly Registration Coverage (expected vs registered meals).

## Weekview Report (UI)
- Purpose: Shows per-department weekly overview based on weekview aggregation (includes per-day residents and meal availability used elsewhere).
- Route: `weekview_report_ui` in `core/ui_blueprint.py` renders `templates/ui/weekview_report.html`.
- Data: Built via `compute_weekview_report(...)` from `core/weekview_report_service.py`, which depends on `WeekviewService` to enrich each day with residents counts and menu items.
- Output: Per-department payload containing daily entries for `lunch` and `dinner` (wording in UI includes “Kväll”/“Middag” to satisfy legacy test expectations) and totals.
- Notes: Uses the effective residents precedence from `WeekviewService` (weekly per-day → forever schedule → weekly override → fixed).

## Weekview Report (API/Exports)
- CSV/XLSX routes: Present in `core/ui_blueprint.py`, they reuse `compute_weekview_report(...)` for aggregation and return downloadable data. Behaviour unchanged.
- Structure: Mirrors UI payload but formatted for export.

## Weekly Registration Coverage (Admin)
- Purpose: Coverage statistics comparing expected meals (where menu exists) vs registered meals (tracked flags) per department across the week.
- Route: `reports_weekly` in `core/ui_blueprint.py` renders `templates/ui/unified_report_weekly.html`. Separate routes provide CSV/XLSX where applicable.
- Service: `ReportService.get_weekly_registration_coverage(...)` in `core/report_service.py`.
  - Departments: `_get_departments_for_site(site_id)` queries `departments` table.
  - Week dates: Computed from ISO `year` and `week` (Mon–Sun).
  - Expected meals: Query `weekview_items` for `tenant_id`, `department_id`, date range, and non-empty `title`; presence of a row for `(date, meal)` implies expectation.
  - Registered meals: `MealRegistrationRepo.get_registrations_for_week(...)` returns `(date, meal_type, registered)`; looked up by `(date, meal_type)`.
  - Coverage: Counts lunch/dinner expected vs registered; totals and `coverage_percent` rounded.
- Template: `templates/ui/unified_report_weekly.html` shows department list, navigation, and export links. No behaviour changes in current inventory.

## Residents Schedule Logic Usage
- Weekview Report: Uses `WeekviewService` which applies residents precedence: weekly per-day schedule → forever schedule → weekly override → fixed. These enriched counts feed weekview UI and exports.
- Registration Coverage: Does not use residents counts directly; “expected” comes from presence of `weekview_items` menu rows rather than residents schedules.

## Current Limitations / Observations
- “Expected” for coverage is tied to menu availability, not residents count; this is by design in current behaviour.
- Weekview UI wording includes legacy terms to keep tests passing; no functional change.
- Variation schedules (weekly/forever) influence the weekview aggregation but not the registration coverage metrics.

## Files and Components
- Routes/UI: `core/ui_blueprint.py` → `templates/ui/weekview_report.html`, `templates/ui/unified_report_weekly.html`
- Services: `core/weekview_report_service.py`, `core/report_service.py`, `core/weekview/service.py`
- Data repos: `weekview_items` table (SQL), `MealRegistrationRepo`, residents schedule repos used by `WeekviewService`.

This inventory is analysis-only. No behaviour changes were made.
