# Unified mapping: Legacy → Unified (Weekview / Report / Admin)

Scope: municipal and offshore modules present in this workspace. Timeboxed, minimal breadth.

## Weekview
- Legacy (Kommun/Offshore): No weekview endpoints found in `modules/municipal` or `modules/offshore`.
- Unified:
  - GET `/api/weekview` (ETag + 304)
  - PATCH `/api/weekview`
  - PATCH `/api/weekview/residents`
  - PATCH `/api/weekview/alt2`
  - Flag: `ff.weekview.enabled`

## Report
- Legacy (Kommun/Offshore): No report endpoints found in `modules/municipal` or `modules/offshore`.
- Unified:
  - GET `/api/report` (read-only; ETag + 304)
  - Flag: `ff.report.enabled`

## Admin foundations
- Legacy (Kommun/Offshore): No admin endpoints found in these modules.
- Unified:
  - Admin feature flags and audit APIs exist under `core/admin_api.py` and `core/admin_audit_api.py`.

## Templates → UI
- Legacy municipal/offshore modules do not include templates in this workspace snapshot for these areas.
- Unified UI is structured under `templates/` (see `_base.html`) and inline UI (`core/inline_ui.py`). For Weekview/Report UX, mapping occurs at API level and is consumed by modern clients.
