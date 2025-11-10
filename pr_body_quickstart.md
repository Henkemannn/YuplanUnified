Wire quickstart links in dashboard widget.

Scope
- In core/templates/ui/dashboard.html (#widget-quickstart):
  - Veckovy -> /weekview
  - Rapport -> /report
  - Planering -> /planning
- RBAC: active links for admin & staff (via "editor" proxy); viewer gets disabled buttons with title="Insufficient permissions".
- Feature flag: ff.dashboard.enabled respected (unchanged).
- No backend logic changed; template-only.

Tests
- Extend tests/test_dashboard_mvp.py:
  - admin/editor: hrefs for /weekview, /report, /planning
  - viewer: no hrefs; disabled buttons + tooltip
  - FF off: 404 still

DoD
- Dashboard 200 with active links for admin/editor
- viewer sees disabled quickstart with tooltip
- All dashboard tests green; no RBAC/FF regressions.
