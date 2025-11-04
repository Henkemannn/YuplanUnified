# Changelog

## 0.3.0 — Phase 3 admin concurrency

- Optimistic concurrency completed across admin resources (users, roles, feature-flags).
- Shared helpers for ETag parsing and RFC7807 `412 Precondition Failed` responses.
- GET supports `If-None-Match` and returns `304 Not Modified` when appropriate.
- PATCH/PUT require `If-Match` only when applying changes; DELETE always requires `If-Match`.
- Strict header validation: invalid `If-Match`/`If-None-Match` → `400 application/problem+json` with `invalid_header`.
- DB guardrails for `updated_at` (defaults, triggers, backfill) to ensure ETag stability.
