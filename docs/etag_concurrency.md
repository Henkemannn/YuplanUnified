# ETag optimistic concurrency (admin)

This project uses weak ETags to coordinate concurrent updates on admin resources.

- ETag format: `W/"<sha1(id:updated_at.isoformat())>"`, where `updated_at` is the database timestamp as stored.
- Resources covered: users, roles (user role view), and feature-flags.

## Round trip

1. GET the resource to read its ETag:
   - Server returns `200` with body and `ETag` header.
   - If you already have an ETag and send `If-None-Match` with the same value (or `*`), server returns `304`.
2. Mutate with optimistic concurrency using `If-Match`:
   - PATCH/PUT: include `If-Match` only when a real change will be applied; no-op updates are allowed without `If-Match`.
   - DELETE: always requires `If-Match`.
   - On mismatch, server returns `412` with an RFC7807 payload including `expected_etag` and `got_etag`.
3. On success, the server returns the updated representation and a new `ETag` header.

## Validation and errors

- `If-Match` / `If-None-Match` must use quoted (or weak) entity tags, e.g. `W/"abcd"` or `"abcd"`. Wildcard `*` is accepted where applicable.
- Invalid or empty header values return `400 application/problem+json` with `invalid_params: [{"name": "If-Match", "reason": "invalid_header"}]`.
- Feature-flags treat `notes: null` and `notes: ""` as equivalent; updating between these is a no-op.

## DB guardrails

- Postgres: `updated_at` has a DEFAULT of `CURRENT_TIMESTAMP` and triggers bump on UPDATE (kept as stored, no timezone coercion).
- SQLite: the app layer updates `updated_at` within the same transaction.
- A migration backfills `updated_at` where NULL.
