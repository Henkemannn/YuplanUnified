Title: Demo UI — CSV export, ARIA tabs, Alt2 ETag badges (staging-only)

Summary
- Adds client-side CSV export in Report tab (UTF-8 BOM, Excel-friendly)
- Improves accessibility: ARIA roles + keyboard navigation for tabs (←/→, Home/End, Enter/Space)
- Shows Alt2 per-row ETag badge (debug), visible only when DEMO_UI=1
- Preserves CSP: no inline JS; assets in /static/demo.js and /static/demo.css

Files touched
- templates/demo_admin.html: data-demo-ui flag, ARIA attributes, Export CSV button
- static/demo.js: CSV export, ARIA keyboard nav, badge rendering, state handling
- static/demo.css: Yuplan palette, focus outline, .alt2-etag style
- core/admin_demo_ui.py: passes demo_ui_enabled to template

Acceptance
- Report: "Läs in" then "Export CSV" downloads report_week_<week>.csv; opens in Excel with headers and data (BOM)
- Tabs: arrow keys move focus; Home/End to first/last; Enter/Space activates; aria-selected/tabindex and hidden panels update correctly
- Alt2: badge shows ETag W/…:vN per row (visible only when DEMO_UI=1); idempotent PUT keeps N; toggle bumps to N+1
- HEAD /demo has Content-Security-Policy + Cache-Control: no-store
- pytest -q: PASS

Out of scope
- Server endpoints unchanged
- No backend report schema changes

Post-merge (staging)
- fly secrets set DEMO_UI=1 STAGING_SIMPLE_AUTH=1 -a yuplan-unified-staging
- fly deploy -a yuplan-unified-staging
- Verify: /demo/ping 200; HEAD /demo headers; smoke.ps1 green; UI CSV + ARIA + badges
