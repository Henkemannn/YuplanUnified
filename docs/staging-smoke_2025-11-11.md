# Staging Smoke – 2025-11-11

Environment: https://yuplan-unified-staging.fly.dev/
DB: Fly Postgres (psycopg v3 URL normalized)
Simple Auth: STAGING_SIMPLE_AUTH=1 (auto-enables `ff.admin.enabled`)

## Context
Seed script (`scripts/seed_varberg_midsommar.py`) provisioned:
- site_id: 5f8e2aea-9060-4981-9686-c70dbc723a11
- departments:
  - cb763847-e326-42cb-8bb4-35a2cb823f52 (version 3 → 4 after PUT)
  - 8c59ae92-8e0b-4919-aaa8-5379d42a07e4
- Alt2 week 51 items (initial version v1 sequence)

## Department Flow
1. GET /admin/departments?site_id=… → 200, ETag `W/"admin:departments:site:<site_id>:v3"`
2. Conditional GET If-None-Match v3 → 304
3. PUT /admin/departments/<dep1> If-Match `W/"admin:dept:<dep1>:v3"` + X-CSRF-Token → 200, item ETag `W/"admin:dept:<dep1>:v4"`
4. GET again collection ETag updated `W/"admin:departments:site:<site_id>:v4"`
5. Conditional GET with new ETag → 304
6. Conditional GET with stale v3 → 200 (updated body)

## Alt2 Week Flow (week=51)
1. GET /admin/alt2?week=51 → 200, ETag `W/"admin:alt2:week:51:v1"`
2. PUT idempotent (same items) If-Match v1 → 200, ETag remains v1
3. PUT toggle one item If-Match v1 → 200, ETag `W/"admin:alt2:week:51:v2"`
4. PUT toggle-back If-Match v2 → 200, ETag `W/"admin:alt2:week:51:v3"` (baseline restored)

## CSRF
Writes required `X-CSRF-Token` header populated from `csrf_token` cookie. Missing header yields 403 under strict mode.

## Errors Resolved Earlier
- Postgres driver mismatch (postgres → postgresql+psycopg) fixed in `core/db.py` + Alembic env.
- Multiple migration heads merged (0009).
- Boolean defaults dialect-aware.
- Alembic version column widened to VARCHAR(128).
- Seed FK failure fixed by diet type upserts.
- Alt2 500 (placeholder site_id) replaced with dynamic department site lookup.

## Verification Checklist
- Health: /health → 200 with feature list including `ff.admin.enabled`
- ETag conditional GET semantics validated (departments & alt2)
- Idempotent update does not bump version (alt2 v1 stays v1)
- Concurrency bump visible on modifying resource (dept v3 → v4; alt2 v1→v2→v3)

## Next Steps
- Merge PR #24 then #25.
- Add automated smoke (PowerShell + optional bash) and login scripts (done).
- Provide demo UI at `/demo` (done) showcasing ETag + CSRF flows.
- Share staging access doc.
