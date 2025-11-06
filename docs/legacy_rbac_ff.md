# Legacy RBAC & Feature Flags (Kommun + Offshore)

Scope: only what exists in this workspace under `modules/municipal` and `modules/offshore`.

## RBAC decorators found

- modules/municipal/views.py
  - `@require_roles("superuser", "admin", "unit_portal", "cook")` on `GET /municipal/menu/week`
  - `@require_roles("superuser", "admin", "cook")` on `POST /municipal/menu/variant`
- modules/offshore/views.py
  - No `@require_roles` decorators present.

## Feature flags referenced

- No explicit feature-flag checks were found in these legacy module files.

## Notes
- In Unified, Weekview is gated by `ff.weekview.enabled` and Report by `ff.report.enabled` (see `core/weekview_api.py` and `core/report_api.py`).
