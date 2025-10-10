# ADR-003: Full RFC7807 Adoption and Legacy Error Retirement

- Title: Full RFC7807 Adoption and Legacy Error Retirement
- Date: 2025-10-09
- Status: Accepted

## Context

- Yuplan core uses mixed error formats: RFC7807 for pilot endpoints and legacy JSON envelopes elsewhere.
- ProblemDetails pilot verified (impersonation, diet, support) with flag `YUPLAN_PROBLEM_ONLY`.
- Legacy `ErrorXXX` schemas still exist in OpenAPI; flag toggles dual behavior.

## Decision

- Adopt RFC7807 (ProblemDetails) as the single standard across all endpoints.
- Remove `YUPLAN_PROBLEM_ONLY` flag and legacy JSON envelopes.
- Retire `ErrorXXX` responses and mark `ProblemXXX` components as canonical.
- All 4xx/5xx responses must conform to RFC7807 core fields + Yuplan extensions (`request_id`, `incident_id`, `errors[]`).
- Preserve `required_role` field in 403 only via `problem.extra`.

## Migration Plan

- Phase 1 (DONE): Pilot rollout verified with mixed mode.
- Phase 2 (NOW): Sweep remaining blueprints (auth, tasks, admin, planning).
- Phase 3: Remove legacy flag, update tests, purge `ErrorXXX` from OpenAPI, bump version `v1.0.0`.

## Consequences

- + Unified error parsing for clients.
- + Simplified backend logic (single handler pipeline).
- + Cleaner OpenAPI spec and docs.
- - Breaks clients relying on legacy envelopes (requires coordinated rollout).

## Verification

- All endpoints return `application/problem+json`.
- OpenAPI validation passes for `ProblemXXX` only.
- All tests for legacy fallback removed/replaced.
- CI gate ensures Content-Type problem+json for every 4xx/5xx.

## References

- ADR-001 (429 Standardization)
- ADR-002 (Strict CSRF Rollout)
- README (Problem Details section)
- SECURITY.md (Error Hygiene)
