# Yuplan Unified v1.2.0 — Backend Stabilization

## Teststatus

- Passed: 827
- Skipped: 8
- Warnings: 3 (benign; OpenAPI validator deprecation)
- No failures; backend is stable.

## What’s Changed

### OpenAPI & Errors
- Spec builds and validates correctly.
- Added missing components: `FeatureFlag`, `Error`, `User`, `UserWithRole`.
- Standardized admin/API errors to RFC7807 ProblemDetails (`status`, `title`, `detail`, `type`).
- Tests migrated off legacy `{ok,error}` envelopes.

### CSRF & RBAC
- Strict CSRF enforced on protected prefixes; missing/invalid → 403 ProblemDetails.
- Admin mutations (users, roles, feature flags) require valid CSRF; blocked before side-effects.
- RBAC: admin/superuser access is correct; viewer/editor → 403; anonymous → 401 ProblemDetails.

### Feature Flags & Tenant
- `TenantFeatureFlag` fields aligned with tests.
- Missing tenant → 401 ("authentication required").
- Admin module off: `/admin/stats` → 404 ProblemDetails (`detail: Admin module is not enabled`).

### Admin Limits
- GET `/admin/limits`: role required (admin/superuser), tenant optional; invalid `tenant_id` → 400; viewer/editor → 403; anonymous → 401.
- POST/DELETE `/admin/limits`: `tenant_id` read from JSON; missing/invalid → 400; no dependency on session tenant.
- Audit/telemetry events emitted for list/upsert/delete.

### Tasks & Legacy Cook
- Task creation: viewer blocked with 403 ProblemDetails.
- Legacy cook requires `allow_legacy_cook_create`; emits one deprecation warning per tenant/day.
- Error shapes harmonized to ProblemDetails across tasks routes.

## Risks
- Low risk: changes align with explicit tests; CSRF/RBAC hardened; error formats standardized.
- No changes in weekview/planera/kitchen modules.

## Rollout
- Tag release as `v1.2.0` and merge to `master`.
- Proceed with UI/UX phases (portal, dashboard, landing) on top of stabilized backend.

## Acknowledgements
Thanks to the contributors for pushing stability across OpenAPI, security, and admin modules.