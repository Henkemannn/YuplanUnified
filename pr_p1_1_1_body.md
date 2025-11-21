## Planera Phase P1.1.1 – Hardening

Scope: Negative tests (flag disabled), Conditional GET (304), diet name tolerance (no strict assertions), week UI department filter groundwork, blueprint registration.

### Changes
- UI routes now return 404 when `ff.planera.enabled` disabled (abort 404 path).
- Added planera blueprint registration in `app_factory`.
- Department filter groundwork in `/ui/planera/week` (validates and restricts aggregation if `department_id` provided; adds `department_filter_id` to VM).
- Tests added:
  - `test_planera_day_flag_disabled.py`, `test_planera_week_flag_disabled.py` (404 when disabled).
  - `test_planera_day_etag_304.py`, `test_planera_week_etag_304.py` (ETag 304 behavior).
  - `test_planera_week_department_filter.py` (groundwork validation).
- Skeleton tests updated to force-enable flag to avoid cross-test leakage.

### Diet Name Tolerance
No assertions on specific diet names; tests only verify structural presence and counts (existing skeleton unaffected).

### Quality
- Full pytest suite: 370 passed, 7 skipped.
- No DB migrations; no changes to Weekview/Report logic.
- Scoped, minimal diffs.

### Labels
module:planera, phase:P1.1.1, type:hardening, area:api, area:ui, ready-for-review

### TODO (Next Phase P1.2)
- Diet registry mapping for user-friendly names.
- Export (print + CSV).
- Enhanced UI rendering for department-filter (optional selector).
