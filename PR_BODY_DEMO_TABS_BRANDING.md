Title: Demo UI: Tabs + Yuplan branding; ETag-aware report; CSP hardening; smoke/OpenAPI fixes

Summary
- Refactors the staging-only /demo UI into tabbed panels (Weekview | Admin | Menyval | Report)
- Adds Yuplan branding and externalizes CSS/JS (no inline JS; CSP-safe)
- Adds read-only Report summary with ETag/304-aware fetching and graceful field handling
- Hardens /demo responses with Cache-Control: no-store
- Restricts /_routes diagnostics behind cookie/header/token gate
- Extends in-app OpenAPI with admin endpoints and If-Match headers expected by tests
- Fixes PowerShell smoke script to handle ETag header arrays and 304 without throwing
- Adds staging-only root redirect / -> /demo when DEMO_UI=1

Scope notes
- Read-only UI. No new write endpoints or database changes.
- CSV/XLSX export deliberately out-of-scope (will follow in a micro-PR if needed).

Acceptance checklist
- [ ] DEMO_UI=1 set in staging; app deploys; /demo reachable with CSP header present
- [ ] /demo/ping returns 200 and {"ok":"true"}
- [ ] Tabs render and switch without inline JS; logo loads from /static/logo/yuplan_logo.svg with CSP-safe fallback
- [ ] Report summary loads for current year/week; respects ETag (304 on conditional) and tolerates missing fields
- [ ] Admin -> Departments conditional GET returns 304 with If-None-Match; PUT bumps ETag; stale If-None-Match returns 200
- [ ] Menyval (Alt2) idempotent PUT keeps ETag; toggling bumps ETag; conditional GET behaves correctly (304/200)
- [ ] /_routes requires yp_demo cookie OR X-Demo-Debug: 1 OR X-Demo-Token=<secret>
- [ ] OpenAPI (/openapi.json) includes /api/admin/* paths and If-Match header params
- [ ] PowerShell smoke succeeds end-to-end using pwsh native commands (no jq/grep)

How to verify (pwsh)
- Login session cookie; then:
  - GET $BaseUrl/demo/ping
  - HEAD $BaseUrl/demo/ (note trailing slash) and check Content-Security-Policy
  - GET $BaseUrl/_routes with X-Demo-Debug: 1 or X-Demo-Token if set
  - Run: pwsh -File scripts/smoke.ps1 -BaseUrl <url> -SiteId <guid> -Week <int>

Security
- CSP: script-src 'self'; no inline JS; all scripts/styles served from /static
- Demo endpoints are behind feature flag (DEMO_UI=1) and set Cache-Control: no-store
- Diagnostics route hardened by cookie/header/token gating

OpenAPI
- Adds /api/admin endpoints: departments (POST/PUT), diet-defaults (PUT), alt2 (PUT/GET), stats (GET)
- Includes If-Match headers for update operations and If-None-Match for conditional reads

Follow-ups
- Optional: client-side CSV export for Report tab
- Optional: Add minimal accessibility tweaks to tabs (aria-selected, role=tablist)
