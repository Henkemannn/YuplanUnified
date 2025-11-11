# Legacy routes — Report (Kommun + Offshore)

Scope: only what exists in this workspace under `modules/municipal` and `modules/offshore`.

## Summary
No legacy Report routes were found in the municipal/offshore modules in this workspace.

## Routes map

| App       | Route | Method | View/Handler | Template | RBAC / Flag checks | Notes |
|-----------|-------|--------|--------------|----------|--------------------|-------|
| municipal | —     | —      | —            | —        | —                  | No report-related endpoints found in `modules/municipal/views.py` |
| offshore  | —     | —      | —            | —        | —                  | No report-related endpoints found in `modules/offshore/views.py` |

## Extraction method
- Grepped for `report`, `rapport`, and `@bp.get`/`@bp.post`. None found.

## Notes
- Unified Report endpoint is implemented at `core/report_api.py`:
  - GET `/api/report` (read-only; conditional GET with ETag; gated by `ff.report.enabled`)
