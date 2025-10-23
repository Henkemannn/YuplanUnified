## RBAC matrix (canonical roles)

This document defines the canonical roles used by the platform and how they map to legacy labels. It also summarizes access expectations per endpoint group and the error semantics (401 vs 403) enforced by the centralized handlers.

### Canonical roles

- superuser — full platform control across tenants (support/ops)
- admin — tenant administrator (manage content and settings within a tenant)
- editor — elevated write access within scope (e.g., unit portal)
- viewer — read-only access

Legacy labels map to canonical via `core/roles.py`:

- cook → viewer
- unit_portal → editor

### Error semantics

- 401 Unauthorized: No authenticated session (missing/invalid token). Raised via `SessionError` and rendered as RFC7807 problem+json with type `https://example.com/errors/unauthorized`.
- 403 Forbidden: Authenticated but lacking required role. Raised via `AuthzError(required=...)` and rendered as RFC7807 with `required_role` in the body and type `https://example.com/errors/forbidden`.

All errors include `request_id` and standard ProblemDetails fields.

### Endpoint groups and required roles

- Superuser API (`/api/superuser/*`, `/superuser/*`)
  - Required: superuser
  - Notes: mutating endpoints also enforce strict CSRF when enabled; send `X-CSRF-Token`.

- Admin APIs (limits, audit, feature flags) under `/admin/*`
  - Typical reads: admin (some lists may allow superuser as well)
  - Mutations: admin (or superuser)

- Tasks and Notes (`/tasks/*`, `/notes/*`)
  - Reads: viewer and above (canonical)
  - Writes: editor and above

- Diet/Menu/Turnus modules
  - Reads: viewer and above
  - Writes: editor and above (some operations reserved for admin/superuser)

### Examples of `@require_roles` usage

- `@require_roles("superuser")` — superuser only
- `@require_roles("admin")` — admin (superuser is not implicitly allowed unless included)
- `@require_roles("superuser", "admin", "unit_portal", "cook")` — allows a mix of canonical and legacy labels; enforcement maps via `to_canonical()`.

See `core/app_authz.py` for the decorator and centralized error handling in `core/errors.py`.
