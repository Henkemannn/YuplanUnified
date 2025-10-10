# Global 429 Standardization

TL;DR: Pilot endpoints return Problem429 with `retry_after` in the body and a `Retry-After` header; legacy endpoints keep the JSON envelope with `retry_after` and `limit`, plus the `Retry-After` header.

## Goal
Unify 429 responses across the platform:
- Pilot (ProblemDetails) paths emit `application/problem+json` with `status=429`, `detail=rate_limited`, and `retry_after` in the payload. Always set `Retry-After` header.
- Legacy paths keep `{ok:false, error:"rate_limited", message, retry_after, limit}` and set `Retry-After` header.

## Runtime Behavior (Pilot vs Legacy)
- Pilot prefixes (RFC7807): `/diet`, `/superuser/impersonate`, `/admin/support` (and later `/auth` when migrated)
  - Content-Type: `application/problem+json`
  - Shape: RFC7807 with `request_id` echoed, optional `errors[]`, and on 429 include `retry_after` (integer seconds)
  - Header: `Retry-After: <seconds>`
- Legacy (everywhere else)
  - Content-Type: `application/json`
  - Shape: `{ok:false, error:"rate_limited", message:"…", retry_after:<int>, limit:<string?>}`
  - Header: `Retry-After: <seconds>`

## Implementation Steps
1) Centralize 429 mapping
- In `core/errors.py` RateLimitError handler:
  - Pilot → `too_many_requests(detail="rate_limited", retry_after=retry_after)`; audit the problem response.
  - Legacy → `_legacy_response(429, "rate_limited", extra={"retry_after": int, "limit": name})` and set `Retry-After` header.
- Replace ad-hoc 429 emitters with this handler where practical, or adapt them to raise `RateLimitError`.

2) Ensure Retry-After header everywhere
- In `core/http_errors.py` `too_many_requests(...)`, set the header when `retry_after` is provided.
- In `core/rate_limit.py` `rate_limited_response(...)`, include JSON `retry_after` and header `Retry-After`.

3) OpenAPI
- Add `components.responses.Problem429` with `Retry-After` header and an example (`retry_after: 30`).
- Ensure pilot paths reference `Problem429`; legacy responses keep `Error429` with JSON schema that includes `retry_after` and `limit` and header doc for `Retry-After`.

4) Tests
- Pilot test: A pilot-scoped endpoint must return `application/problem+json` with `status=429` and `retry_after` in the body; header `Retry-After` present.
- Legacy test: A non-pilot endpoint must return JSON envelope with `error:"rate_limited"`, `retry_after` (int), `limit` (if known), and `Retry-After` header.
- Keep token bucket and fixed window integration tests; ensure `rate_limit.hit` metrics tags include `strategy` correctly.

5) Rollout
- No breaking change for legacy consumers (JSON remains). Pilot consumers see RFC7807 (already in pilot scope).
- If client constraints exist, gate via `YUPLAN_PROBLEM_ONLY` and pilot prefixes.

6) Commit Messages
- feat(errors): standardize 429 across pilot+legacy (Problem429 on pilot, JSON on legacy)
- docs(openapi): Problem429 + Retry-After examples and mappings
- test: assert retry_after field + header on 429 (pilot and legacy)
- docs: README/SECURITY/CHANGELOG 429 semantics update
