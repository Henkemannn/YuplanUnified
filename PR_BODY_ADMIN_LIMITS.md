# feat(admin): GET/POST/DELETE /admin/limits — inspect & override rate limits

## Summary
Adds admin inspection endpoint `GET /admin/limits` plus write endpoints `POST /admin/limits` (upsert tenant override) and `DELETE /admin/limits` (idempotent removal). GET supports pagination and optional filters (`tenant_id`, `name`). Returns effective rate limits with their resolution source (`tenant`, `default`, `fallback`).

## Details
- Resolution order: tenant override → global default → fallback (5/60)
- Listing semantics:
  * Without `tenant_id`: list only global defaults (omit fallback noise)
  * With `tenant_id`: union of default names + tenant override names
  * `name` filter: if explicit and not found in defaults/overrides, show single fallback row (source=`fallback`)
- OpenAPI additions: `LimitView`, `PageResponse_LimitView`, `LimitUpsertRequest`, `LimitDeleteRequest`, `LimitMutationResponse`, path `/admin/limits`
- Pagination: standard `page`, `size` (capped at 100) returning `meta {page,size,total,pages}`
- Docs: README + CHANGELOG sections updated (usage + behavior)

## API Shapes
`LimitView`:
```jsonc
{
  "name": "export_csv",
  "quota": 5,
  "per_seconds": 60,
  "source": "default", // tenant|default|fallback
  "tenant_id": 42        // only when tenant_id context provided
}
```
`PageResponse_LimitView` standard wrapper: `{ ok, items: LimitView[], meta }`.

## Tests
New: `tests/test_admin_limits_api.py`, `tests/test_admin_limits_write_api.py`
- 401 unauthenticated
- 403 viewer role
- defaults listing (no tenant_id)
- tenant override listing (source=tenant)
- fallback on explicit unknown name
- pagination slice

All tests: 196 passed, 3 skipped.

## Type / Lint
- Strict pockets unchanged; no new mypy errors
- OpenAPI spec build path exercised by existing spec tests

## Risk
Low: Write endpoints are scoped to admin role, in-memory registry update only (no persistent side-effects beyond process memory). Existing resolution order unchanged.

## Rollout / Observability
Optional future telemetry: increment `admin.limits.view` with tags (`tenant_id` present?, filtered?).

## Review Checklist
- [ ] OpenAPI: `LimitView`, `PageResponse_LimitView`, `LimitUpsertRequest`, `LimitDeleteRequest`, `LimitMutationResponse` finns och refereras i `/admin/limits`.
- [ ] Auth: 401/403 täcks av tester (viewer/unauth).
- [ ] Semantik: fallback endast vid explicit name.
- [ ] Pagination: meta.page/size/total/pages korrekta.
- [ ] Clamp: quota≥1, 1≤per_seconds≤86400 verifierade i tester.
- [ ] Idempotens: DELETE returnerar removed: bool.
- [ ] Registry: resolution order (tenant→default→fallback) bibehållen.
- [ ] Docs: README/CHANGELOG uppdaterade.

## Follow-ups (separate PRs suggested)
- Telemetry for admin limits view/upsert/delete
- Audit logging for limit mutations
- Caching layer if usage grows (nuvarande map lookup O(1) räcker nu)
