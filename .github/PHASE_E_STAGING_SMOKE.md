# Phase E — Staging Smoke Checklist

1) Health + OpenAPI
- GET $HOST/health → 200 {"status":"ok"}
- GET $HOST/openapi.json → 200; info.version = 1.9.0

2) Seed tenant
- Run: `make seed-varberg` (DATABASE_URL set to staging DB)
- Expect printed site/department IDs and ETags

3) Admin writes (ETag/412)
- GET `departments?site=<siteId>` → capture ETag A
- PUT `departments/{id}` (If-Match from GET/HEAD) → 200 + new ETag B
- GET `departments?site=<siteId>` with `If-None-Match: A` → 200 + ETag B

4) Diet defaults
- GET `diet-defaults?department=<depId>` → capture ETag
- PUT diet-defaults (diff payload, If-Match) → 200 + new ETag

5) Alt2 (week 51)
- GET `alt2?week=51` → capture ETag W
- PUT alt2 (identical payload, If-Match=W) → 200 + same ETag (idempotent)
- PUT alt2 (toggle one flag, If-Match=W) → 200 + new ETag W'

6) Notes
- GET `notes?scope=site&site_id=<siteId>` → 200 + ETag
- PUT notes (If-Match) → 200 + new ETag

7) Frontend cache (manual)
- Load DepartmentsPage → refresh → confirm no visual blink (304 path)
