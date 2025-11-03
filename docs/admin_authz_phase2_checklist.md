# Admin AuthZ Phase 2 – Checklist

## ✅ Acceptance Criteria (Phase 2) — all met

- ✅ RBAC on admin endpoints (admin-only for mutations via `require_roles`)
- ✅ CSRF enforcement on /admin mutations (header `X-CSRF-Token` validated centrally)
- ✅ 422 for validation errors and 404 for not-found with details
- ✅ RFC7807 on admin errors (application/problem+json for 401/403/404/422)
- ✅ OpenAPI updated for users/roles/feature-flags (+ CsrfToken on mutations)
- ✅ Audit events on mutations (user_create, user_update_role, feature_flag_update, user_update_email)
- ✅ Admin test suite green (CI + local)

### Ready for Merge checklist

- [ ] CI green on admin test suite
- [ ] OpenAPI validate green
- [ ] Phase 2 branch rebased onto default
- [ ] Draft PR converted to Ready-for-Review
- [ ] Squash-merge with title: `feat(admin-authz-phase2): complete migration + RFC7807`

This checklist prepares the next batch after RC1 is merged. It assumes base = `feat/admin-limits-inspection` (default branch) and focuses on migrating additional admin endpoints to `app_authz`, tightening RFC7807 responses, and enriching OpenAPI examples.

## Progress (2025-11-01)
- Users
   - GET: implemented list with pagination-stub headers and case-insensitive `?q=` email substring filter.
   - POST: RBAC/CSRF enforced; 422 validation (email format, role enum, no additional props); duplicate email → 422; happy-path persists to DB.
- Feature-flags
   - GET: list with `?q=` filter (key/notes, case-insensitive); pagination-stub headers.
   - PATCH: 422 validation, 404 on unknown key (tenant-scoped), persists `enabled/notes` and `updated_at` (UTC).
- Roles
   - GET: list (same shape as users) with pagination-stub headers.
   - PATCH: 422 validation, 404 on unknown user (tenant-scoped); persists role and `updated_at` (UTC); idempotent.
- OpenAPI
   - Paths for users/feature-flags/roles; CsrfToken on mutations; 403 examples; added 200 examples for lists and roles PATCH.
   - Documented pagination stub (`page/size`) on lists and `q` param on users/feature-flags lists.
- Tests (pytest)
   - RBAC, CSRF, validation, not-found, persistence happy-paths; list endpoints + pagination-stub header behavior; `?q=` filters for flags and users.
- Pending/Near-term
   - Optional: Roles GET `?q=` (mirror users); UI hints (CSRF/rights) in admin views; Users DELETE (soft-delete) for test-data cleanup.

<!-- ci: re-run markdownlint after config changes -->
<!-- ci: re-run again after MD023 disable -->

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

## Post-RC1 kickoff sequence (quick)
1) Rebase/sync
   - Run `scripts/make_phase2_branch.ps1` to refresh `feat/admin-authz-phase2` from default.
2) Route stubs + guards (all 3 endpoints)
   - Goal: endpoints exist; 401/403 flow through central handling.
   - Temporarily return simple 200/201 stub bodies (or 501 if preferred) — replaced later.
   - Commit per endpoint (small diffs).
3) OpenAPI – minimal paths + security hooks
   - Add paths + CsrfToken on mutations + one 403 example per endpoint.
   - Keep schemas minimal (reuse `User`, `ProblemDetails`; add small `Update*Request` as needed).
4) Tests — staged
   - Start with RBAC (unauth=401, viewer=403).
   - Then CSRF (mutations without token → 401/403 per policy).
   - Then 422/404 validation.
   - Finally happy path.

### Commit message patterns
- feat(admin-authz): stub /admin/users with require_roles("admin")
- feat(admin-authz): stub /admin/feature-flags with admin guard
- feat(admin-authz): stub /admin/roles with admin guard
- docs(openapi): add minimal paths for users/feature-flags/roles with CsrfToken on mutations
- test(admin): RBAC for users/feature-flags/roles (401/403)
- test(admin): CSRF enforcement on mutations
- test(admin): validation (422) and not-found (404) scaffolding
- test(admin): happy path smoke for users/flags/roles
- chore(ci): ensure openapi-validate includes new admin paths

### Copilot prompt pack (paste into editor for diffs)
1) Route stubs + guards
   - Users: add GET/POST under admin blueprint, decorate with require_roles("admin"); GET returns {items:[], total:0} (200), POST returns {id:"stub", email:"stub", role:"viewer"} (201).
   - Feature-flags: add GET/PATCH; guard with require_roles("admin"); GET returns {items:[], total:0} (200); PATCH returns {key:"<path_key>", enabled:false, notes:""} (200).
   - Roles: add GET/PATCH; guard with require_roles("admin"); GET returns {items:[], total:0} (200); PATCH returns {id:"<user_id>", role:"viewer"} (200).
   - Hint: set blueprint prefix "/admin" if not centralized; import from app_authz; central problem helpers handle 401/403 before handlers.
2) OpenAPI minimal
   - Add paths for users (GET+POST), feature-flags (GET + PATCH {key}), roles (GET + PATCH {user_id}); attach CsrfToken to mutations; add one 403 example per endpoint.
   - Reuse ProblemDetails, UnauthorizedProblem, ForbiddenProblem, CsrfToken security.
3) Tests (stage 1: RBAC)
   - For each endpoint: GET unauth→401; GET viewer→403 with required_role=admin; POST/PATCH unauth→401; POST/PATCH viewer→403.

### Definition of Done (per endpoint)
- [ ] Route guard in place: require_roles("admin") on all ops.
- [ ] RBAC tests: unauth=401; viewer=403 with required_role=admin (+ invalid_params echo).
- [ ] CSRF enforced on mutations (tests assert 401/403 per policy).
- [ ] Validation 422: invalid payloads return ProblemDetails with invalid_params.
- [ ] Not Found 404 for unknown key/id where applicable.
- [ ] OpenAPI updated: paths, params, CsrfToken on mutations, at least one 403 example.
- [ ] Happy path covered with minimal success body.
- [ ] CI green: tests, typecheck/lint, openapi-validate.


---

## Endpoint 1: /admin/users (GET + POST)

### Scope
- GET `/admin/users` — list users for current tenant.
- POST `/admin/users` — create user (minimal: email, role). Requires CsrfToken.
- Both routes protected by `app_authz.require_roles("admin")`.
- Unified RFC7807 for 401/403 and validation errors.
- OpenAPI: 403 example (viewer → admin) and POST with CsrfToken security and request/response schemas.

### Acceptance Criteria (/admin/users)
- Guard: `require_roles("admin")` on GET/POST.
- 401 → type, title, status=401.
- 403 → type, title, status=403, `required_role=admin`, `invalid_params=[{ name:"required_role", value:"admin"}]`.
- 422 (validation): `invalid_params=[{ name:"email", reason:"invalid_format"}]`, etc.
- OpenAPI: `/admin/users` documented; POST has `security: [ { CsrfToken: [] } ]` and hint “Fetch via GET /csrf…”.
- Tests (CI Py 3.12):
   - viewer → 403 with `required_role=admin`
   - unauth GET/POST → 401
   - POST without CSRF → 401/403 per policy (recommended 401 "missing/invalid CSRF" if distinguished)
   - POST invalid payload → 422 with `invalid_params`
   - Happy path (admin) → 200/201 with expected body
- Lint/Typecheck PASS. OpenAPI-validate green.

### Migration steps (small, isolated commits)
1) Route guard
    - Add `@require_roles("admin")` on both endpoints.
    - Reuse established error model.
2) RFC7807 responses
    - Wire 401/403 via centralized helpers (same as `/admin/units`).
3) CSRF on POST
    - Mark POST as mutation; ensure middleware validates header `X-CSRF-Token`.
4) OpenAPI
    - Add paths, requestBody schema, responses, security-scheme reference.
    - Add 403 example `viewer_hitting_admin`.
5) Unit tests
    - RBAC, CSRF, validation, happy-path.

### OpenAPI (YAML fragment)
```yaml
paths:
   /admin/users:
      get:
         summary: List users for current tenant
         tags: [Admin]
         security:
            - BearerToken: []
         responses:
            '200':
               description: OK
               content:
                  application/json:
                     schema:
                        type: object
                        properties:
                           items:
                              type: array
                              items:
                                 $ref: '#/components/schemas/User'
                           total:
                              type: integer
            '401':
               $ref: '#/components/responses/UnauthorizedProblem'
            '403':
               description: Forbidden (requires admin)
               content:
                  application/problem+json:
                     schema:
                        $ref: '#/components/schemas/ProblemDetails'
                     examples:
                        viewer_hitting_admin:
                           value:
                              type: "about:blank"
                              title: "Forbidden"
                              status: 403
                              required_role: "admin"
                              invalid_params:
                                 - { name: "required_role", value: "admin" }
      post:
         summary: Create a user in current tenant
         tags: [Admin]
         security:
            - BearerToken: []
            - CsrfToken: []   # <— Important
         requestBody:
            required: true
            content:
               application/json:
                  schema:
                     $ref: '#/components/schemas/CreateUserRequest'
         responses:
            '201':
               description: Created
               content:
                  application/json:
                     schema:
                        $ref: '#/components/schemas/User'
            '400':
               $ref: '#/components/responses/BadRequestProblem'
            '401':
               $ref: '#/components/responses/UnauthorizedProblem'
            '403':
               $ref: '#/components/responses/ForbiddenProblem'
            '422':
               description: Unprocessable Entity
               content:
                  application/problem+json:
                     schema:
                        $ref: '#/components/schemas/ProblemDetails'
                     examples:
                        invalid_email:
                           value:
                              type: "about:blank"
                              title: "Validation error"
                              status: 422
                              invalid_params:
                                 - { name: "email", reason: "invalid_format" }
components:
   securitySchemes:
      CsrfToken:
         type: apiKey
         in: header
         name: X-CSRF-Token
         description: >
            Required for mutations. Fetch via GET /csrf to obtain a token.
   schemas:
      User:
         type: object
         required: [id, email, role]
         properties:
            id: { type: string, format: uuid }
            email: { type: string, format: email }
            role: { type: string, enum: [admin, editor, viewer] }
            created_at: { type: string, format: date-time }
      CreateUserRequest:
         type: object
         required: [email, role]
         properties:
            email: { type: string, format: email }
            role: { type: string, enum: [admin, editor, viewer] }
```

### RFC7807 – examples
- 401 (unauth):
```json
{ "type": "about:blank", "title": "Unauthorized", "status": 401 }
```

- 403 (viewer → admin-route):
```json
{
   "type": "about:blank",
   "title": "Forbidden",
   "status": 403,
   "required_role": "admin",
   "invalid_params": [{ "name": "required_role", "value": "admin" }]
}
```

- 422 (validation):
```json
{
   "type": "about:blank",
   "title": "Validation error",
   "status": 422,
   "invalid_params": [{ "name": "email", "reason": "invalid_format" }]
}
```

### Test skeleton (pytest)
Create `tests/admin/test_admin_users.py` later when implementing:
```python
import pytest


def test_get_users_unauth_returns_401(client):
      r = client.get("/admin/users")
      assert r.status_code == 401
      body = r.get_json()
      assert body["status"] == 401


def test_get_users_viewer_returns_403(client, auth_headers):
      r = client.get("/admin/users", headers=auth_headers(role="viewer"))
      assert r.status_code == 403
      body = r.get_json()
      assert body["status"] == 403
      assert body["required_role"] == "admin"
      assert {"name": "required_role", "value": "admin"} in body["invalid_params"]


def test_post_users_requires_csrf(client, auth_headers):
      payload = {"email": "new.user@example.com", "role": "editor"}
      # missing CSRF:
      r = client.post("/admin/users", json=payload, headers=auth_headers(role="admin"))
      assert r.status_code in (401, 403)
      # with CSRF:
      headers = auth_headers(role="admin")
      headers["X-CSRF-Token"] = "valid-csrf-token"
      r2 = client.post("/admin/users", json=payload, headers=headers)
      assert r2.status_code in (200, 201)
      body = r2.get_json()
      assert body["email"] == payload["email"]
      assert body["role"] == payload["role"]


@pytest.mark.parametrize("bad_payload,expected_name", [
      ({"email": "not-an-email", "role": "editor"}, "email"),
      ({"email": "ok@example.com", "role": "not-a-role"}, "role"),
])
def test_post_users_validation_422(client, auth_headers, bad_payload, expected_name):
      headers = auth_headers(role="admin")
      headers["X-CSRF-Token"] = "valid-csrf-token"
      r = client.post("/admin/users", json=bad_payload, headers=headers)
      assert r.status_code == 422
      body = r.get_json()
      assert any(p.get("name") == expected_name for p in body.get("invalid_params", []))
```

### Checklist (to tick when implementing)
- [ ] `/admin/users` GET/POST migrated to `app_authz` (admin).
- [ ] RFC7807 401/403/422 as above.
- [ ] POST requires `CsrfToken`; UI hint updated where relevant.
- [ ] OpenAPI: paths + 403 example + CsrfToken security + request/response schemas.
- [ ] Unit tests: RBAC (401/403), CSRF, validation 422, happy path 201.
- [ ] CI: tests & openapi-validate green.

---

## Endpoint 2: /admin/feature-flags (GET + PATCH)

### Scope
- GET `/admin/feature-flags` — list all flags for current tenant (supports `q=` quick filter).
- PATCH `/admin/feature-flags/{key}` — toggle/update metadata for a flag (e.g., enabled, notes). Mutation → CsrfToken required.
- Both routes protected by `app_authz.require_roles("admin")`.
- Unified RFC7807 for 401/403/404/422.
- OpenAPI with 403 example (viewer → admin); PATCH has `CsrfToken` security + hint.

### Acceptance Criteria
- Guard: `require_roles("admin")` on GET & PATCH.
- GET supports `?q=` as case-insensitive substring filter on key and description.
- PATCH validates body (allowed only: `enabled: bool`, `notes: string<=500`).
- 401/403 per established model with `required_role=admin`.
- 404 when flag key is missing.
- 422 for validation errors (e.g., wrong type for enabled, notes too long).
- OpenAPI: paths documented; PATCH has `security: [ { CsrfToken: [] } ]`; 403 example; path parameter `{key}` defined.
- Tests (CI Py 3.12): RBAC (viewer→403, unauth→401), CSRF (PATCH without token → 401/403 per policy), 404, 422, happy path.
- Lint/Typecheck PASS. OpenAPI-validate green.

### Migration steps (small commits)
1) Routes + guard: GET/PATCH with `@require_roles("admin")`.
2) Query filter: apply `q=` in repo/service layer (new or existing).
3) RFC7807: 401/403/404/422 via centralized helpers.
4) CSRF: PATCH requires `X-CSRF-Token`.
5) OpenAPI: paths/params/schemas/security + 403 example.
6) Tests: RBAC/CSRF/404/422/happy-path.

### OpenAPI (YAML fragment)
```yaml
paths:
   /admin/feature-flags:
      get:
         summary: List feature flags for current tenant
         tags: [Admin]
         security: [ { BearerToken: [] } ]
         parameters:
            - in: query
               name: q
               schema: { type: string }
               description: Case-insensitive substring filter on key/description
         responses:
            '200':
               description: OK
               content:
                  application/json:
                     schema:
                        type: object
                        properties:
                           items:
                              type: array
                              items: { $ref: '#/components/schemas/FeatureFlag' }
                           total: { type: integer }
            '401': { $ref: '#/components/responses/UnauthorizedProblem' }
            '403':
               description: Forbidden (requires admin)
               content:
                  application/problem+json:
                     schema: { $ref: '#/components/schemas/ProblemDetails' }
                     examples:
                        viewer_hitting_admin:
                           value:
                              type: about:blank
                              title: Forbidden
                              status: 403
                              required_role: admin
                              invalid_params: [ { name: required_role, value: admin } ]
   /admin/feature-flags/{key}:
      patch:
         summary: Update a feature flag (enable/notes)
         tags: [Admin]
         security:
            - BearerToken: []
            - CsrfToken: []
         parameters:
            - in: path
               name: key
               required: true
               schema: { type: string }
         requestBody:
            required: true
            content:
               application/json:
                  schema: { $ref: '#/components/schemas/UpdateFeatureFlagRequest' }
         responses:
            '200':
               description: Updated
               content:
                  application/json:
                     schema: { $ref: '#/components/schemas/FeatureFlag' }
            '401': { $ref: '#/components/responses/UnauthorizedProblem' }
            '403': { $ref: '#/components/responses/ForbiddenProblem' }
            '404':
               description: Not Found
               content:
                  application/problem+json:
                     schema: { $ref: '#/components/schemas/ProblemDetails' }
            '422':
               description: Validation error
               content:
                  application/problem+json:
                     schema: { $ref: '#/components/schemas/ProblemDetails' }
components:
   schemas:
      FeatureFlag:
         type: object
         required: [key, enabled]
         properties:
            key: { type: string }
            description: { type: string }
            enabled: { type: boolean }
            notes: { type: string, maxLength: 500 }
            updated_at: { type: string, format: date-time }
      UpdateFeatureFlagRequest:
         type: object
         additionalProperties: false
         properties:
            enabled: { type: boolean }
            notes:   { type: string, maxLength: 500 }
```

### RFC7807 – examples
- 403 (viewer):
```json
{ "type":"about:blank","title":"Forbidden","status":403,
   "required_role":"admin",
   "invalid_params":[{"name":"required_role","value":"admin"}] }
```

- 404 (unknown flag):
```json
{ "type":"about:blank","title":"Not Found","status":404,"detail":"feature flag not found" }
```

- 422 (validation):
```json
{ "type":"about:blank","title":"Validation error","status":422,
   "invalid_params":[{"name":"notes","reason":"too_long"}] }
```

### Test skeleton (pytest)
Save as `tests/admin/test_feature_flags.py`.
```python
import pytest


def test_list_flags_unauth_401(client):
      r = client.get("/admin/feature-flags")
      assert r.status_code == 401


def test_list_flags_viewer_403(client, auth_headers):
      r = client.get("/admin/feature-flags", headers=auth_headers(role="viewer"))
      assert r.status_code == 403
      body = r.get_json()
      assert body["required_role"] == "admin"


def test_list_flags_filter_q(client, auth_headers):
      r = client.get("/admin/feature-flags?q=beta", headers=auth_headers(role="admin"))
      assert r.status_code == 200
      body = r.get_json()
      assert "items" in body


def test_patch_flag_requires_csrf(client, auth_headers):
      r = client.patch(
            "/admin/feature-flags/some-flag",
            json={"enabled": True},
            headers=auth_headers(role="admin"),
      )
      assert r.status_code in (401, 403)  # per CSRF policy


def test_patch_flag_happy_path(client, auth_headers):
      headers = auth_headers(role="admin"); headers["X-CSRF-Token"] = "valid"
      r = client.patch(
            "/admin/feature-flags/some-flag",
            json={"enabled": False, "notes": "Rolling back"},
            headers=headers,
      )
      assert r.status_code == 200
      body = r.get_json()
      assert body["key"] == "some-flag"
      assert body["enabled"] is False


def test_patch_flag_404(client, auth_headers):
      headers = auth_headers(role="admin"); headers["X-CSRF-Token"] = "valid"
      r = client.patch(
            "/admin/feature-flags/does-not-exist",
            json={"enabled": True},
            headers=headers,
      )
      assert r.status_code == 404


@pytest.mark.parametrize("payload,expected", [
      ({"enabled": "yes"}, "enabled"),               # wrong type
      ({"notes": "x"*501}, "notes"),                 # too long
      ({"unknown": "field"}, "unknown"),             # disallowed
])
def test_patch_flag_422(client, auth_headers, payload, expected):
      headers = auth_headers(role="admin"); headers["X-CSRF-Token"] = "valid"
      r = client.patch("/admin/feature-flags/some-flag", json=payload, headers=headers)
      assert r.status_code == 422
      body = r.get_json()
      # either invalid_params.name == expected, or generic "additionalProperties not allowed"
      assert "invalid_params" in body
```

### Checklist (to tick when implementing)
- [ ] `/admin/feature-flags` GET/PATCH guarded by `app_authz` (admin).
- [ ] GET supports `?q=` quick filter (key/description).
- [ ] PATCH requires `CsrfToken` and validates allowed fields.
- [ ] RFC7807 401/403/404/422 per examples.
- [ ] OpenAPI: paths, params, 403 example, CsrfToken security, request/response schemas.
- [ ] Unit tests: RBAC/CSRF/404/422/happy path.
- [ ] CI green: tests, typecheck/lint, openapi-validate.


<!-- lint: markdownlint configured via .markdownlint.json; long lines permitted for tables and examples -->

## Endpoint 3: /admin/roles (GET + PATCH)

### Scope (lean but useful)
- GET `/admin/roles`: list users + their roles for current tenant (supports `q=` on email).
- PATCH `/admin/roles/{user_id}`: change role (`admin|editor|viewer`) for a given user. Mutation → CsrfToken required.
- Guard: `require_roles("admin")` on both.

### Acceptance Criteria
- RBAC: unauth → 401, viewer → 403 with `required_role=admin` (+ `invalid_params` echo).
- PATCH body: `{ role: "admin|editor|viewer" }` only (no extra fields).
- 404 if `user_id` not found in tenant.
- 422 for invalid role or extra fields.
- CSRF required for PATCH via `X-CSRF-Token`.
- OpenAPI: paths/params; `security: [BearerToken, CsrfToken]` on PATCH; 403 example (viewer→admin); 404/422 examples; `UserRoleUpdate` schema with `additionalProperties: false`.
- CI: tests green on Py 3.12; OpenAPI‑validate green; lint/typecheck PASS.

### Work steps (small commits)
1) Routes & guard
   - Add GET `/admin/roles` and PATCH `/admin/roles/<user_id>` under an admin blueprint.
   - Decorate with `@require_roles("admin")`.
2) Query/filter
   - GET: optional `?q=` substring (case‑insensitive) against email.
3) RFC7807
   - Reuse central helpers: 401/403; 404 (unknown user); 422 (validation/extra field).
4) CSRF
   - PATCH must validate `X‑CSRF‑Token` (middleware enforced).
5) OpenAPI
   - Define `UserWithRole` and `UserRoleUpdate` schemas; set `additionalProperties: false` for update.
   - Add security: `[BearerToken, CsrfToken]` for PATCH and a 403 example with `required_role=admin`.
6) Tests
   - Create `tests/admin/test_roles.py` to cover: GET unauth=401; viewer=403; admin=200 (+ `?q=` filter); PATCH unauth=401; viewer=403; no CSRF=401/403; 404 unknown user; 422 invalid role/extra field; happy path 200.

### Minimal data contracts (OpenAPI, not code)
- `UserWithRole`: `id: uuid`, `email: email`, `role: enum[admin,editor,viewer]`, `updated_at: date‑time`.
- `UserRoleUpdate`: required `role`; enum as above; `additionalProperties: false`.

### Checklist (to tick when implementing)
- [ ] `/admin/roles` GET/PATCH guarded by `app_authz` (admin).
- [ ] GET supports `?q=` on email; returns filtered result.
- [ ] PATCH requires `CsrfToken`; only `{ role }` allowed; updates role.
- [ ] RFC7807 401/403/404/422 per AC.
- [ ] OpenAPI: paths/params/security + examples; `UserRoleUpdate` schema.
- [ ] Unit tests: RBAC, CSRF, 404, 422, happy path.
- [ ] CI green across tests/typecheck/lint/OpenAPI.

