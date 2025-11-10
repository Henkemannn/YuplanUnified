# feat(admin): Phase B — persistence, ETag/412 writes, alt2 bulk

## Summary
Implements Admin Phase B write-path with optimistic concurrency and Alt2 bulk persistence.

- OpenAPI version bump: info.version → 1.8.0
- Changelog updated with a new "Admin Phase B" entry (Added/Changed).
- Backward compatibility: Read endpoints and previous clients remain unaffected; new write paths are additive and flag-gated.

## What’s in
- Alembic 0008_admin_phase_b.py:
  - version + updated_at + triggers for PG/SQLite (no-op safe in SQLite)
  - alt2_flags with PK (site_id, department_id, week, weekday), CHECK week 1..53, weekday 1..7, FKs ON DELETE CASCADE
  - Indexes: (department_id, week) and (week, department_id, weekday)
- Repositories (admin_repo.py): Sites, Departments, Notes, DietDefaults, Alt2
  - Alt2: idempotent upsert (ON CONFLICT … DO UPDATE … WHERE IS DISTINCT FROM)
  - collection_version(week) → collection-ETag `W/"admin:alt2:week:{week}:v{n}"`
- ETag utilities (etag.py): make_etag, parse_if_match, ConcurrencyError
- Service (admin_service.py):
  - update_alt2_bulk(if_match, week, items) with validation and collection ETag
  - helpers to expose current_etag for 412 responses
- API (admin_api.py):
  - All writes require If-Match and return ETag; 412 includes `current_etag`
  - PUT /api/admin/alt2 uses collection ETag and returns per-item ETags
- OpenAPI (admin.yml):
  - Updated headers + examples for If-Match/ETag; 412 ProblemDetails examples include `current_etag`
- Tests:
  - ETag happy/stale (departments, diet-defaults)
  - RBAC 403 for non-admin writes
  - Alt2 idempotency + collection-ETag stability (no bump on identical payload, bump on toggle)
  - SQLite parity; OpenAPI header presence

## Checklist
- [x] PG/SQLite migrations pass in CI matrix
- [x] Repos implement optimistic concurrency
- [x] Admin endpoints require If-Match and return ETag
- [x] OpenAPI updated (headers + 412 ProblemDetails + examples)
- [x] Tests green (baseline + Phase B)
- [x] Alt2 idempotency and collection ETag stability verified
- [x] Staging smoke checklist attached in PR comment

## Risk / Rollback
Additive migration; safe rollback by dropping alt2_flags and triggers. Alt2 bulk is idempotent; repeated identical PUT safe.
