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

