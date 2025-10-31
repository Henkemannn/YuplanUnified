# Admin AuthZ Phase 2 – Checklist

This checklist prepares the next batch after RC1 is merged. It assumes base = `feat/admin-limits-inspection` (default branch) and focuses on migrating additional admin endpoints to `app_authz`, tightening RFC7807 responses, and enriching OpenAPI examples.

## Scope
- Migrate remaining Admin routes to `app_authz.require_roles(["admin"])` with consistent RFC7807 401/403.
- Add OpenAPI examples for Admin endpoints (403 examples, CsrfToken security for mutating operations).
- Extend tests to lock in behavior (unit tests only; E2E tracked separately).

## Acceptance criteria
- All Admin endpoints consistently enforce role=admin via shared decorator.
- RFC7807 401/403 include: type, title, status, detail (when helpful), `required_role`, and `invalid_params` entry `{ name: "required_role", value: "admin" }` for 403.
- OpenAPI `/admin/*` paths present with: 403 example for GETs; CsrfToken security for POST/PUT/PATCH/DELETE.
- Unit tests pass on CI (Ubuntu, Python 3.12). No regressions to Superuser or public APIs.

## Tasks
1) Inventory Admin endpoints
   - List current Admin routes and classify: read-only vs mutating.
2) Decorate endpoints
   - Apply `app_authz.require_roles(["admin"])` to all Admin routes.
   - Ensure errors map through centralized RFC7807 handler.
3) RFC7807 parity
   - Verify 401/403 envelopes include `required_role` and `invalid_params` (admin) as per spec.
4) OpenAPI enrichment
   - Add `/admin/*` paths with:
     - GET: 403 example (viewer) and standard responses.
     - Mutations: `security: [ { CsrfToken: [] } ]` and examples.
5) Tests (unit)
   - Add/extend tests to cover:
     - GET as viewer → 403 + fields.
     - POST unauth → 401.
     - POST as admin without CSRF (if enforced on admin scope) → 403/400 accordingly.
6) Docs
   - Link checklist from README and docs/modules.md when PR is opened.
7) CI
   - Ensure tests workflow runs on branch. Keep Python 3.12.

## Out of scope (tracked separately)
- E2E for Admin UI flows.
- Seeding/fixtures for specific modules beyond minimal test data.

## Rollout plan
- Open PR: "Admin AuthZ Phase 2 – migrate endpoints + OpenAPI examples".
- Keep commits small and logical. Ensure OpenAPI diff is reviewed.
- Merge when CI green. Follow up with E2E issues.

