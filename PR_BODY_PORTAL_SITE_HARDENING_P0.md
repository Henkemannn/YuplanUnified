# P0 HARDENING: Portal ignores query site_id for customer admins

## Summary
- Customer admins (site-bound roles) cannot switch site via querystring in the portal.
- Only systemadmin/superuser may use `site_id` in the query (for admin/debug).
- Tests updated to either use superuser for query `site_id` scenarios or bind session site to match.
- New regression test ensures customer admin ignores query `site_id`.

## Details
- `core/ui_blueprint.py`:
  - `portal_week`: Non-superusers always use `session["site_id"]` and ignore query `site_id`. Superuser may use query and falls back to session when missing.
  - `portal_week_save`: Only superuser can target arbitrary `site_id`. Customer roles overwrite posted `site_id` with `session["site_id"]` regardless of `site_lock`.
- Tests updated/added:
  - Adjusted Phase 1/3 portal tests to bind session site or use superuser when query `site_id` is required.
  - Added `tests/ui/test_portal_customer_admin_query_site_hardening_p0.py::test_portal_customer_admin_ignores_query_site_id`.

## Why
- GDPR isolation and tenant/site scoping: customer admins must not pivot sites via querystring.
- Maintains superuser tooling for debugging/admin flows while keeping default portal behavior safe.

## Validation
- Full test suite passes: 918 passed, 11 skipped, 3 warnings (OpenAPI deprecation warnings unchanged).
- Targeted tests:
  - `test_portal_customer_admin_ignores_query_site_id` (new) ✅
  - `test_portal_site_lock_session_site_phase4.py` ✅
  - `test_portal_week_phase1.py` (adjusted where applicable) ✅
  - `test_portal_department_week_ui_phase3.py::test_navigation_data_attrs_present` (superuser) ✅

## Notes
- No API shape changes; behavior change limited to site scoping enforcement in portal week routes.
- Kitchen/grid routes remain unaffected aside from shared viewmodel consumption.
