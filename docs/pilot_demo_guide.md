# Yuplan Unified — Pilot Demo (Internal)

## Scope
- **Admin**: create/edit Departments, set Diet Defaults (diff save), toggle Alt2 (bulk)
- **Weekview**: visualize Alt2 (yellow), correct menu per day
- **Report**: correct counts per week (lunch/dinner), ignores Alt2 in statistics

## Flow (10–12 min)
1. Login → Dashboard (Yuplan wordmark visible)
2. Admin → Departments: rename "Avd 1" (show If-Match/ETag in DevTools network panel)
3. Diet Defaults: change one amount → Save (only changed amounts applied)
4. Alt2: pick week 51 → tick 1–2 boxes → Save (ETag changes); immediately save again with no change (ETag stable)
5. Weekview: show Alt2 highlights; switch days to confirm diff
6. Report: select week 51; verify counts and warnings; confirm Alt2 not altering static totals
7. Notes: edit site note (If-Match) → reload to show persistence

## Appendix
### ETag Formats
- Single resource: `W/"admin:dept:<id>:vN"`
- Collection: `W/"admin:departments:site:<site-id>:vN"`
- Alt2 week: `W/"admin:alt2:week:<week>:vN"`

### 412 Recovery UX
- PUT with stale `If-Match` → 412 + `current_etag` in ProblemDetails
- Client re-fetches, updates local cache, retries mutation

### 304 Cache Behavior
- Second GET with matching `If-None-Match` → 304 (empty body) + same ETag
- Frontend reuses cached data → no UI blink

### Contacts
Henrik Jonsson <henrik@yuplan.se>
