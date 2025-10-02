# Decision Record: Standard Pagination Envelope

Date: 2025-10-01
Status: Accepted

## Context
Multiple list endpoints (`/tasks/`, `/notes/`) previously returned raw arrays without consistent metadata. Clients need stable pagination semantics (total pages, deterministic ordering) for infinite scroll and export preflight.

## Decision
Introduce a unified JSON pagination envelope:

```
{
  "ok": true,
  "items": [ ... ],
  "meta": {
    "page": 1,
    "size": 20,
    "total": 137,
    "pages": 7
  }
}
```

Query parameters (shared contract):
- `page` (1-based, default 1)
- `size` (default 20, min 1, max 100 – values >100 are clamped to 100)
- `sort` (optional, currently reserved / ignored in v1; included for forward compatibility)
- `order` (`asc` | `desc`, default `asc`, only applied when `sort` becomes active)

## Ordering Semantics
For deterministic slicing the backend applies a stable composite ordering when querying:
1. Primary: `created_at` descending
2. Secondary tie-breaker: `id` descending

This ensures newly created rows appear first and pagination does not duplicate / skip items when new rows arrive between requests.

## Defaults & Caps
- Default page: 1
- Default size: 20
- Hard cap size: 100 (requests above are clamped silently)

## Error Policy
Invalid numeric inputs or values < 1 for `page` / `size` raise a `400` mapped to error envelope:
```
{ "ok": false, "error": "bad_request", "message": "page must be >= 1" }
```
(Exact `message` text may vary per validation branch; clients should rely on `error`.)

Invalid `order` values fallback to `asc` instead of erroring (robustness choice; may tighten later if needed).

## Non-Goals (Current Iteration)
- Server-side arbitrary field sorting (reserved `sort` param)
- Cursor-based pagination (offset-based acceptable for current scale)
- Embedded hypermedia links (`next`, `prev`) – clients can derive via `meta`.

## Alternatives Considered
1. Raw array + `X-Total-Count` header – rejected (harder for clients behind CORS caches; multi-value metadata desires JSON).
2. Cursor tokens – premature given small dataset size & need for immediate deterministic upgrade.
3. Per-endpoint bespoke envelopes – rejected to reduce cognitive overhead.

## Impact
- Existing clients must adapt to new envelope (breaking change intentionally accepted; no BC shim maintained).
- OpenAPI components added: `PageMeta`, `PageResponse_Tasks`, `PageResponse_Notes`.
- Encourages reuse for future list endpoints (menus, attendance logs, metrics snapshots).

## Follow-Up / Future Work
- Implement `sort` whitelisting (e.g., `sort=created_at|updated_at`) with validation.
- Add cursor-based mechanism when row counts exceed performance thresholds.
- Introduce link relations or HATEOAS extension if frontend pagination logic becomes complex.
- Consolidate duplicated stable ordering logic into query builder utilities.

## References
- Implementation: `core/pagination.py`
- Tests: `tests/test_pagination.py`
- OpenAPI spec generation: `core/app_factory.py`
