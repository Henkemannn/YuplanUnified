# Legacy routes — Weekview (Kommun + Offshore)

Scope: only what exists in this workspace under `modules/municipal` and `modules/offshore`.

## Summary
No explicit legacy Weekview routes were found in the municipal/offshore modules in this workspace. See table below and notes.

## Routes map

| App       | Route | Method | View/Handler | Template | RBAC / Flag checks | Notes |
|-----------|-------|--------|--------------|----------|--------------------|-------|
| municipal | —     | —      | —            | —        | —                  | No weekview-related endpoints found in `modules/municipal/views.py` |
| offshore  | —     | —      | —            | —        | —                  | No weekview-related endpoints found in `modules/offshore/views.py` |

## Extraction method
- Grepped for `@bp.get`, `@bp.post`, `week`, `weekview`, and references to templates/macros; only menu-related endpoints were present in municipal.

## Notes
- Unified Weekview lives under `core/weekview_api.py` with endpoints:
  - GET `/api/weekview` (conditional GET with ETag)
  - PATCH `/api/weekview`
  - PATCH `/api/weekview/residents`
  - PATCH `/api/weekview/alt2`
- Feature flag: `ff.weekview.enabled` gates these in Unified.
