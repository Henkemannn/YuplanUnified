# Legacy routes — Admin foundations (Kommun + Offshore)

Scope: only what exists in this workspace under `modules/municipal` and `modules/offshore`.

## Summary
No legacy Admin foundation routes were found in the municipal/offshore modules in this workspace.

## Routes map

| App       | Route | Method | View/Handler | Template | RBAC / Flag checks | Notes |
|-----------|-------|--------|--------------|----------|--------------------|-------|
| municipal | —     | —      | —            | —        | —                  | No admin-related endpoints found in `modules/municipal/views.py` |
| offshore  | —     | —      | —            | —        | —                  | No admin-related endpoints found in `modules/offshore/views.py` |

## Extraction method
- Grepped for `admin`, `@bp.get`, `@bp.post`. None found in these modules.

## Notes
- Unified Admin endpoints exist elsewhere in the codebase (e.g., `core/admin_api.py`, `core/admin_audit_api.py`). This mini-harvest focuses strictly on municipal/offshore legacy modules.
