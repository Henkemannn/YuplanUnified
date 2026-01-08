# P0 SECURITY: Weekview site-lock enforcement

Summary
- Enforce site-lock for bound admins in `ui.weekview_ui`: ignore querystring `site_id`, use session-bound site.
- Do not load sites list when locked; VM now includes `allow_site_switch` flag (false when locked) and `sites=[]`.
- Hide "Byt site" UI in `weekview_all.html` unless `allow_site_switch` is true.

Behavior
- Bound admin cannot switch site via querystring; content remains on bound site.
- No other site names render in HTML for locked users.
- Unbound/systemadmin behavior unchanged; site switcher visible.

Tests
- Added `tests/ui/test_weekview_site_lock.py::test_weekview_site_lock_ignores_query_switch`.
- Full suite passes locally: 884 passed, 11 skipped.

Files
- core/ui_blueprint.py
- templates/ui/weekview_all.html
- tests/ui/test_weekview_site_lock.py

Risk
- Low; scoped to weekview UI and VM.
