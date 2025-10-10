# ADR-002: Strict CSRF Rollout

- Title: Strict CSRF Rollout
- Date: 2025-10-09
- Status: Accepted

## Context

- Mixed CSRF posture historically (some forms, some fetch)
- We added flag-gated strict CSRF (header `X-CSRF-Token` + form `csrf_token`, exempt health/auth callbacks)
- RFC7807 + audit in place; pilot stable

## Decision

- Enable strict CSRF by default (feature flag on in prod)
- Standardize token issue/rotation (per-session; rotate daily)
- Enforce on POST/PUT/PATCH/DELETE with central `before_request` guard
- Exempt: `/health`, SSO callbacks, static assets
- Failures return RFC7807 (csrf_missing / csrf_invalid), include `request_id`; audit `problem_response`

## Migration Plan

- Phase 1 (pilot): diet + impersonation (DONE)
- Phase 2: support + auth (toggle-ready)
- Phase 3: enable globally, remove legacy bypasses, update docs

## Consequences

- + Predictable client posture, fewer CSRF regressions
- + Clear dev ergonomics (Jinja helper + fetch meta)
- - Requires header wiring in custom clients

## Verification

- Green tests: header path, form path, exempt paths, flag-off mode
- CI gate: pilot routes must emit `application/problem+json` on CSRF failures

## References

- README (Problem Details Pilot)
- SECURITY (CSRF section)
- OpenAPI Problem responses (403 csrf_* types)
