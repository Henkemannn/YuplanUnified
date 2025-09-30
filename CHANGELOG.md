# Changelog

## [0.3.0] - 2025-09-30 (Auth Hardening & Security)
### Security / Auth
- JWT auth (access ~10m, refresh ~14d) with refresh rotation & replay protection via stored `refresh_token_jti`.
- New endpoints: `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`.
- RBAC enforcement: user (own tasks), admin (tenant-wide), superuser (cross-tenant & feature flag targeting) with task ownership checks.
- In-memory rate limiting buckets: `tasks_mutations`, `feature_flags_admin` + forced test hooks (`X-Force-Rate-Limit*`).
- Standardized 401 / 403 / 429 OpenAPI reusable responses; added BearerAuth security scheme & security arrays on protected paths.
- Centralized task status transition audit logging (`core.audit`).
- Security headers: CSP, HSTS (non-debug/non-test), X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy.

### Domain & Spec
- Task creation 201 + Location header.
- Task.status column + migration (backfill from legacy done) and expanded enum (todo|doing|blocked|done|cancelled).
- OpenAPI examples for create/update/invalid status; 429 responses on rate-limited endpoints.

### Developer Experience
- README Auth Quickstart (login, refresh rotation, RBAC, rate limits, CSP note).
- Added dedicated auth / RBAC / rate limit test suite.
- Audit helper for consistent transitions logging.

### Notes / Future
- CSP still allows `'unsafe-inline'` temporarily (UI refactor planned to remove).
- Rate limiter currently in-memory; plan Redis backend for multi-process scaling.

## Earlier (Scaffold Phase & 0.2.x)
- Initial schema + Alembic baseline.
- Unified error model and OpenAPI error components.
- Feature flags with tenant overrides + admin endpoints.
- Notes & Tasks basic CRUD + inline UI.
- UI enhancements: status pill, spinner styling, toast dedupe.
- CI publishes `openapi.json` artifact & summary.
