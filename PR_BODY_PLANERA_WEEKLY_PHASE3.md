# Planera Weekly Phase 3

## Summary
- Adds weekly Planera UI: GET `/ui/planera/week` with filters (week/day/meal), summary, and departments table.
- Adds mark-all endpoint: POST `/ui/planera/week/mark_all` to mark registrations done for selected departments and meal on a given date.
- Introduces `PlaneraWeeklyService` aggregations: residents, specials by diet, normal counts, and done-state from diet marks and registrations.
- Template includes print stylesheet (`media="print"`), “Skriv ut” button, “Exportera CSV” link; header shows site name; copy aligned to tests.
- Feature flag guard: `ff.planera.enabled` via `current_app.feature_registry` + tenant overrides with `g.tenant_feature_flags`.
- Tests: `tests/ui/test_unified_planera_week_phase3.py`; skeleton/flag/print expectations satisfied; full suite green (748 passed).

## Implementation
- `core/ui_blueprint.py`: GET/POST weekly routes with RBAC and feature flag guards.
- `core/planera_service.py`: `PlaneraWeeklyService` (weekly view + mark-all) and VM dataclasses.
- `templates/planera_week_phase3.html`: filters, summary, department table; print actions and CSV link.

## QA
- Verified with `pytest -q`: 748 passed, 8 skipped.
- Copy alignment: title and header include “Planera – vecka” and “Planering – vecka”.

## Flag Behavior
- UI routes return 404 when `ff.planera.enabled` is disabled (including tenant override via `g.tenant_feature_flags`).

## Notes
- Minimal changes outside Planera;
- CSRF handled via `csrf_token_input` macro.
