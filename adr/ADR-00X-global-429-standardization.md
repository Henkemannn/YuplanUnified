# ADR-00X: Global 429 Standardization

- Title: Global 429 Standardization
- Date: 2025-10-09
- Status: Accepted

## Context

Prior to this change, HTTP 429 responses were inconsistent across the platform:
- Some endpoints returned a legacy JSON envelope with varying fields.
- Some emitted custom headers (or none) without a standardized `Retry-After`.
- Pilot (RFC7807) endpoints and non-pilot endpoints diverged in structure, making client logic brittle and documentation confusing.

The lack of a unified contract made it hard for clients to implement reliable backoff and retry behavior, and complicated our OpenAPI documentation and test coverage.

## Decision

Unify 429 (Too Many Requests) semantics across the platform with two shapes depending on pilot scope, while aligning shared semantics:

1) Pilot endpoints (Problem Details / RFC7807):
   - Response media type: `application/problem+json`
   - Problem type: Problem429
   - Body includes `retry_after` (integer seconds; ceil-rounded; minimum 1)
   - Header `Retry-After: <seconds>` MUST be present

2) Legacy endpoints (non-pilot paths):
   - Response media type: `application/json`
   - Body: `{ "ok": false, "error": "rate_limited", "message": "...", "retry_after": <int>, "limit": "<name>" }`
   - Header `Retry-After: <seconds>` MUST be present

Centralization:
- All 429 responses are produced via a unified `RateLimitError` handling path in `core/errors.py`, ensuring consistent headers and fields for both modes.
- Deterministic test-only endpoints exist to validate both shapes (pilot and legacy) without flakiness.

OpenAPI:
- Pilot paths document `Problem429` under `application/problem+json`.
- Legacy paths keep the existing JSON envelope examples and have clear notes on `retry_after` and `Retry-After`.

Scope notes:
- Pilot endpoints currently include: Superuser Impersonation, Diet writes, and Support. Auth remains legacy during the pilot.

## Consequences

- Consistent client retry and backoff logic across the API surface area.
- No breaking changes for legacy consumers: existing envelope preserved with additive fields.
- Simplified documentation and examples: canonical Problem429 (pilot) and enriched legacy JSON (non-pilot).
- Clear spec ⇄ runtime alignment verified by tests; easier expansion of the pilot later.

## References

- docs/429-standardization.md
- CHANGELOG.md (Unreleased)
- README.md (Problem Details Pilot)
- tests/test_rate_limit_contracts.py
