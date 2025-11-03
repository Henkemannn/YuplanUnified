# Admin AuthZ Phase 3 – Checklist

## Goals
- Wire up full happy-path behavior for admin endpoints introduced in Phase 2:
  - Users: real repo/service for list/create/patch/put/delete, duplicate checks, updated_at,
    pagination headers, filters.
  - Roles: role updates with audit, validation, idempotency.
  - Feature-flags: list + patch (enabled/notes), audit, `updated_at` updates.
- Ergonomics and UI hints: CSRF guidance, required role, quick filters (`q=`), and header totals.
- Keep RFC7807 and OpenAPI in sync (examples, CsrfToken on mutations).
- CI stays green with explicit admin test gate and OpenAPI validation.

## Acceptance Criteria
- All /admin endpoints read/write real data via service/DB layers (no stubs left).
- Validation 422 (invalid_params) and 404 Not Found follow RFC7807 on admin routes (401/403/404/422).
- Audit events emitted appropriately (user_create, user_update_role, user_update_email, feature_flag_update).
- OpenAPI paths and examples updated; CI openapi-validate green.
- Admin unit test suite remains green on CI (Ubuntu, Python 3.12).

## Ready for Merge checklist
- [ ] CI green (admin tests)
- [ ] OpenAPI validate green
- [ ] Branch rebased onto default
- [ ] Draft → Ready for review
- [ ] Squash-merge with title: `feat(admin-authz-phase3): wire real behavior + OpenAPI`

## Suggested Branch
- Base: `feat/admin-limits-inspection` (default)
- New branch: `feat/admin-authz-phase3`
- Helper: `scripts/make_phase3_branch.ps1`

## Work Plan (high-level)
1) Users endpoints
   - GET: DB-backed list with `q=` filter and stub-pagination headers
   - POST: validation + duplicate email check; audit `user_create`
   - PATCH/PUT: validation, idempotency, `updated_at`, audits on role/email changes
   - DELETE: soft-delete (`deleted_at`) and idempotency
2) Feature-flags
   - GET: DB-backed list with `q=`; headers for totals (optional)
   - PATCH: validate allowed fields, persist, `updated_at`, audit
3) Roles
   - GET: list users + roles
   - PATCH: validate role, persist, `updated_at`, audit
4) OpenAPI
   - Update request/response schemas and examples; CsrfToken on mutations
5) Tests
   - Happy-path + edge 422/404 for users/flags/roles; pagination/headers where relevant
6) CI
   - Keep admin-gate and OpenAPI validate required

## Quick Start
- Create branch:
  - Windows PowerShell:
    ```powershell
    pwsh ./scripts/make_phase3_branch.ps1
    ```
- Start implementing per plan above; small focused commits; keep CI green.
