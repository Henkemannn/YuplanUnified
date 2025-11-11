Add If-None-Match/304 to admin GET endpoints (sites, departments, diet-defaults, alt2, notes)
OpenAPI bumped to 1.9.0; examples for ETag/If-None-Match and 304 responses
Optimistic concurrency stays for PUT (If-Match/412), 412 includes current_etag
Frontend: fetchIfNoneMatch + hooks updated; no UI blink on 304
Tests: pytest (PG+SQLite) 200→304→200, Vitest green
CI: Python 3.11 + Node 20; runs pytest + vitest
Removed admin_alt.yml fallback; file left as deprecated stub until CI proves no reference

Checklist:
- [ ] admin.yml loads (no fallback) and matches backend
- [ ] All admin GETs return 304 with matching ETag
- [ ] Frontend uses cached data on 304
- [ ] PG/SQLite parity green
- [ ] CI green (backend+frontend)

Risk/Rollback:
Additive, backward compatible; safe to revert if needed.

Staging smoke (ETag flow):

# Capture ETag
curl -i "$HOST/api/admin/departments?site=<site-id>"
# second GET with If-None-Match should 304
curl -i "$HOST/api/admin/departments?site=<site-id>" -H 'If-None-Match: W/"admin:departments:site:<site-id>:vX"'
# bump via write
curl -i -X PUT "$HOST/api/admin/departments/<dep-id>" \
  -H 'If-Match: W/"<dep-ver>"' -H 'Content-Type: application/json' \
  -d '{"name":"Avd 1 – Öst"}'
# old If-None-Match now yields 200 + new ETag
curl -i "$HOST/api/admin/departments?site=<site-id>" -H 'If-None-Match: W/"admin:departments:site:<site-id>:vX"'