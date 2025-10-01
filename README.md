# Yuplan Unified Platform (Scaffold)

<p align="left">
  <img alt="Ruff" src="https://img.shields.io/badge/Ruff-E,F,I,B,UP,Q-success?logo=python&logoColor=white" />
  <img alt="Mypy" src="https://img.shields.io/badge/Mypy-0%20errors-brightgreen" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-blue" />
</p>

This repository scaffold is the starting point for merging the Municipal (Kommun) and Offshore Yuplan applications into a single multi-tenant, module-driven platform.

## Vision
Provide a Core domain (Menus, Diets, Attendance, Users, Tenants) with optional modules activated per customer (turnus scheduling, waste metrics, prep/freezer tasks, messaging, alt1/alt2 workflow, etc.). Superusers can enable modules on demand.

## Structure
```
unified_platform/
  core/              # app factory, config, models, services stubs
  modules/
    municipal/       # kommun-specific endpoints (placeholder)
    offshore/        # offshore-specific endpoints (placeholder)
  docs/              # architecture, data model, migration & roadmap
  migrations/        # alembic scaffold + env.py
  requirements.txt
  alembic.ini
  .env.example
  run.py
  README.md
```

## Quick Start (Dev)
1. Create virtualenv & install deps:
   ```
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
2. Copy .env.example to .env and adjust values.
3. Run initial migrations (schema is migration-driven; DEV_CREATE_ALL is deprecated):
   ```
   alembic upgrade head
   ```
4. Start app:
   ```
   python run.py
   ```
5. Visit http://localhost:5000/health

### Notes on Migrations
* All schema changes go through Alembic revisions (no runtime create_all in production/dev after bootstrap).
* Flask debug reloader may log each Alembic upgrade step twice (parent + reloader child). This is cosmetic as long as second pass is a no-op.
* To rebuild from scratch in dev:
  ```
  Remove-Item .\app.db -ErrorAction SilentlyContinue
  alembic upgrade head
  ```

### Migration Workflow
1. Make / adjust model classes in `core/models.py`.
2. Generate a new revision (autogenerate picks up diffs):
  ```
  alembic revision --autogenerate -m "describe_change"
  ```
3. Inspect the generated script under `migrations/versions/`:
  - Ensure only intended tables/columns are created/altered.
  - For SQLite compatibility avoid adding columns with non-constant defaults (e.g. CURRENT_TIMESTAMP). Instead: add nullable column, backfill, optionally add NOT NULL constraint in a follow-up DB that supports it.
4. Apply migration:
  ```
  alembic upgrade head
  ```
5. Run tests:
  ```
  pytest -q
  ```
6. If rollback needed (dev only):
  ```
  alembic downgrade -1
  ```

### Timestamp Conventions
* `created_at` / `updated_at` are stored as UTC (application sets `datetime.now(UTC)`).
* For backfilled migrations we may leave columns nullable to simplify cross-database support.
* Avoid relying on database-side auto-updating triggers; updates handled in application layer.

### Export Endpoints
* Admin-only CSV streaming:
  - `/export/notes.csv?sep=;&bom=1`
  - `/export/tasks.csv?sep=,&bom=0`
* Parameters:
  - `sep` — field delimiter (default `,`, use `;` for some regional Excel locales)
  - `bom=1` — prepend UTF-8 BOM for Excel
* Streaming uses generator + `yield_per` for low memory footprint.

### Continuous Integration (CI)
The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs on pushes and pull requests targeting `main` / `master`.

Steps performed:
1. Checkout repository
2. Set up Python 3.11 with pip cache
3. Install dependencies (`pip install -r requirements.txt`)
4. Run database migrations: `alembic upgrade head` (against an ephemeral SQLite database)
5. Execute tests: `pytest -q`
6. (Placeholder) Archive / report stage for coverage or JUnit can be added

Guidelines:
* Always include a migration in the same PR as model changes.
* If CI fails on migration: reproduce locally by deleting your dev DB + rerunning `alembic upgrade head`.
* Consider adding coverage / linting (ruff, mypy) in future steps.

## Developer Tooling: Linting & Typing
Quality gates are being phased in. Keep the repo green (no new warnings) and avoid expanding ignore lists.

### Ruff (Python Linter)
Current active rule sets: `E` (errors), `F` (pyflakes), `I` (imports), `B` (bugbear), `UP` (pyupgrade), `Q` (quotes). Configuration lives in `pyproject.toml` under `[tool.ruff.lint]`.

Common commands:
```
ruff check .                # run lint (CI equivalent)
ruff check . --fix          # apply safe autofixes
ruff check core/ modules/   # scope to changed paths
```
Guidelines:
* Prefer fixing code over adding ignores. Temporary bulk ignores live only for legacy and tests (multi-statement cleanup phase).
* Broaden rules in small batches (already completed Phase 1: added B, UP, Q). Document each expansion in CHANGELOG.
* Keep core and modules free of `B904`, `B007`, `E402`, unused-variable violations (currently clean).

### Mypy (Type Checking)
Early adoption uses a staged approach: critical core modules are type-checked; legacy / peripheral paths are temporarily silenced with `ignore_errors = True` entries in `mypy.ini`.

Run locally:
```
mypy core modules
```
Contribution rules:
* New or modified functions should have explicit return types.
* Avoid `Any` in new code; prefer precise typing or `cast()` when narrowing.
* Do not blanket-add `# type: ignore`; if needed, add a short reason (e.g. `# type: ignore[var-annotated]  # third-party attr added at runtime`).

Phasing plan:
1. Shrink ignore list directory-by-directory.
2. Eliminate `no-any-return` issues in core services.
3. Enable stricter mypy flags (e.g. `warn-return-any`, `disallow-any-generics`) once outstanding returns are cleaned.
4. Eventually move selected domains (auth, tasks, menus) to `strict = True` blocks.

### CI Integration
The lint / type gate runs in a dedicated workflow: `.github/workflows/lint-type.yml` (Ruff first, then Mypy). The general test workflow remains in `.github/workflows/ci.yml`.

PR Checklist (developer self-check):
1. `ruff check .` passes with no new violations.
2. `mypy core modules` shows no increased error count (preferably reduced).
3. Added / changed public functions include type annotations.
4. No new `# type: ignore` without justification.

### Future Tightening (Roadmap)
| Phase | Action | Notes |
|-------|--------|-------|
| 1 | (Done) Add Ruff rules: `B` (bugbear), `UP` (pyupgrade) | Landed with minor manual fixes |
| 2 | (Done) Add `Q` (quotes); future: `PIE`, `SIM` | Enabled; ~legacy/test cleanup pending |
| 3 | Remove one ignore_errors block per sprint | Track delta in PR description |
| 4 | Enable `warn-return-any` globally | Should reach near-zero prior |
| 5 | Turn on `strict = True` for core/* gradually | Start with auth & rate limiting |
| 6 | Introduce runtime type enforcement (optional) | Pydantic / dataclasses where helpful |

### Quick Reference
| Task | Command |
|------|---------|
| Lint check | `ruff check .` |
| Lint autofix | `ruff check . --fix` |
| Type check (core) | `mypy core modules` |
| Both (approx CI) | Run lint then type commands above |

If you add dependencies that affect typing (e.g., new third-party libs), ensure stub packages are installed (`types-<package>` where needed) or add precise `TypedDict` / `Protocol` shims locally.

### Pre-commit Hooks
Install and run the automated hooks locally before pushing:

```
pip install pre-commit
pre-commit install
pre-commit run -a
```

Hooks configured:
* `ruff` (with `--fix`) + `ruff-format`
* `mypy` (scoped to `core` and `modules`)
* Merge conflict marker guard

CI mirrors these checks (lint-type workflow). A green `pre-commit run -a` should guarantee passing lint/type steps in PR.

### Strict Typing Pockets
We adopt full `strict = True` mypy gradually via “pockets” — a focused set of modules that must remain 0-error under strict settings. This avoids boiling the ocean while guaranteeing steady quality expansion.

Current strict pockets (all `strict = True` in `mypy.ini`):
Pocket 1 (foundation):
 - `core.jwt_utils`
 - `core.rate_limit`
 - `core.audit`
 - `core.db`

Pocket 2 (service layer expansion):
 - `core.portion_recommendation_service`
 - `core.menu_service`
 - `core.service_metrics_service`

Pocket 3 (auth & flags hardening):
 - `core.auth`
 - `core.feature_flags`
 - Token payload `AccessTokenPayload` / `RefreshTokenPayload` with explicit required claims & issuer literal.
 - Feature flag registry now typed (`FlagDefinition`, `FlagState`) with safe idempotent `add()` supporting string shorthand.

Expansion workflow (for a new module, e.g. `core.menu_service`):
1. Remove (or avoid adding) its `ignore_errors` block in `mypy.ini`.
2. Add a `[mypy-core.menu_service]` section with `strict = True`.
3. Run: `mypy core/menu_service.py` and fix:
  * Missing return types
  * `Any` leaks (introduce `TypedDict`, `Protocol`, or generics)
  * Unannotated calls to untyped helpers (type those helpers first)
4. Ensure zero errors; commit with message style: `chore(types): strict pocket +menu_service`.

Guidelines:
* Keep commits small (1–2 modules per PR).
* Prefer precise domain types (`TypedDict` for payloads, small dataclasses, `Protocol` for injected services) over `Any`.
* If a dependency is untyped and noisy, isolate usage behind a thin, typed wrapper instead of sprinkling `# type: ignore`.

Tracking: Each added pocket should update this list and optionally a CHANGELOG entry under “Internal”.

### Definition of Done (Typing / Quality PRs)
For any PR expanding strict typing or touching security-critical code:
1. All modified modules pass `mypy` (0 new errors) and strict pocket modules remain clean.
2. `ruff check .` introduces no new violations (run with `--fix` locally first).
3. New data structures expressed via `TypedDict` / `Literal` where shape or finite domain matters.
4. Negative path tests added for security & edge conditions (e.g., missing JWT claims, expired/nbf, unknown feature flag).
5. README & CHANGELOG updated when adding/removing a strict pocket or altering token / flag semantics.
6. PR description lists which pocket(s) affected and summarizes decisions (link or add entry in `DECISIONS.md`).
7. No unexplained `# type: ignore`; any remaining includes rationale comment.
8. Fast pocket-only type workflow (GH Action) green before requesting review.

---

## Next Implementation Tasks
1. Add Alembic initial revision (now scaffolded; generate revision).
2. Implement password hashing & login (core.auth module).
3. Replace in-memory menu service with DB-backed CRUD.
4. Implement municipal endpoints (weekly menu + alt1/alt2 selection logic).
5. Implement import/export (Word parser reuse, DOCX daily export).
6. Add turnus scheduling strategies (port rotation.py logic) under offshore module.
7. Implement waste metrics endpoints & portion recommendation blending.
8. Add reporting queries: diet distribution, attendance summary, menu coverage.
9. (DONE) Introduce tenant_feature_flags table & admin toggling endpoint.
10. Write migration scripts to pull data from legacy SQLite DBs (see docs/migration_plan.md).

## Feature Flags (Initial Seed)
Current registry (secure by default – unknown flags are False):

- menus, diet, attendance (core)
- module.municipal, module.offshore
- turnus, waste.metrics, prep.tasks, freezer.tasks, messaging
- export.docx, import.docx
- openapi_ui (enables Swagger UI at /docs/)

## Design Principles
- No duplication: each domain implemented once in Core or a specific Module.
- Migrations explicit (no runtime ALTER TABLE hacks).
- Small, composable services behind blueprints.
- Tenant isolation by foreign key (future: per-tenant schemas or RLS if needed).

## Documentation
### API Documentation (Swagger UI)
Interactive API docs are served at `/docs/` (Swagger UI) and load the minimal OpenAPI document from `/openapi.json`.

Feature flag: `openapi_ui` (if disabled returns 404). Flag can be toggled via `/features/set`.

Example enable (admin session or test header injection):
```
POST /features/set { "name": "openapi_ui", "enabled": true }
```

The OpenAPI spec is currently a hand-maintained subset; extend `openapi.json` generation in `core/app_factory.py` for new endpoints.
See docs/ for full architecture, data model, migration plan, module definitions, roadmap, deployment guidance.

## Error Model
All API error responses share a compact, stable JSON envelope:

```json
{ "error": "validation_error", "message": "title required" }
```

Fields:
- `error` (string): machine code (e.g. `bad_request`, `validation_error`, `not_found`, `forbidden`, `conflict`, `internal_error`).
- `message` (string): human-readable summary (no PII / stack traces).

Examples:
```jsonc
// 400
{ "error": "bad_request", "message": "Bad Request" }
// 404
{ "error": "not_found", "message": "Resource not found" }
```

Clients should branch on `error` not status text. Additional fields may be added later (e.g. `request_id`) but existing keys stay stable.

## Tasks Domain: status vs done
`status` is the authoritative state field. Enum (current, frozen pending team review):

```
todo | doing | blocked | done | cancelled
```

`done` (boolean) is legacy/read-only (derived as `status == "done"`).

Guidelines:
1. Clients MUST NOT send `done` in create/update payloads – use `status`.
2. If `status` omitted on create the server defaults to `todo`.
3. Legacy clients still sending `{ "done": true }` are mapped to `status: done` (response always includes both for now).
4. Invalid status values return `400 validation_error` with the allowed list.

Minimal How-To:
* Create task (see OpenAPI example `createTask`): send `{"title":"Chop onions","task_type":"prep","status":"todo"}`.
* Progress task (example `updateStatus`): `PUT /tasks/{id}` with `{ "status": "doing" }` (or any allowed value).
* Inspect status in list responses under `task.status`; ignore `task.done` except for backward compatibility.

Refer to `/openapi.json` examples for concrete request/response bodies.

### Status Endpoint Notes
`POST /tasks/` returns **201 Created** with a `Location: /tasks/{id}` header and body `{ ok, task }`.
Clients SHOULD treat `status` as authoritative and ignore `done` for writes.

### Deployment Note
Ensure Alembic migration `0002_add_task_status` has been applied (`alembic upgrade head`) before relying on `status`.

## Feature Flags & Tenant Scoping
Two layers:
1. Global registry (defaults false unless seeded): menus, diet, attendance, module.* namespaces, turnus, waste.metrics, prep.tasks, freezer.tasks, messaging, export.docx, import.docx, openapi_ui, inline_ui.
2. Per-tenant overrides in `tenant_feature_flags` (admin/superuser control).

Admin API endpoints (documented in OpenAPI):

| Method | Path | Purpose | Notes |
|--------|------|---------|-------|
| POST | `/admin/feature_flags` | Toggle feature for tenant | superuser: may pass `tenant_id`; admin: own tenant only |
| GET  | `/admin/feature_flags` | List enabled flags | `tenant_id` query param only for superuser |

Payload (POST):
```json
{ "name": "inline_ui", "enabled": true }
```
Superuser targeting another tenant:
```json
{ "name": "inline_ui", "enabled": true, "tenant_id": 5 }
```

Legacy endpoints `/features`, `/features/check`, `/features/set` remain for simple test flows but new automation should favor the admin endpoints.

## Curl Examples
Assuming local server & authenticated session cookie (or test headers in CI).

Create a task with status:
```bash
curl -X POST http://localhost:5000/tasks/ \
  -H 'Content-Type: application/json' \
  -b cookie.txt \
  -d '{"title":"Prep veggies","task_type":"prep","status":"todo"}'
```

Toggle a feature (admin on own tenant):
```bash
curl -X POST http://localhost:5000/admin/feature_flags \
  -H 'Content-Type: application/json' \
  -b cookie.txt \
  -d '{"name":"inline_ui","enabled":true}'
```

Superuser toggling another tenant (tenant 7):
```bash
curl -X POST http://localhost:5000/admin/feature_flags \
  -H 'Content-Type: application/json' \
  -b su.txt \
  -d '{"name":"inline_ui","enabled":false,"tenant_id":7}'
```

List flags (superuser for tenant 7):
```bash
curl 'http://localhost:5000/admin/feature_flags?tenant_id=7' -b su.txt
```

List flags (admin – own tenant only):
```bash
curl http://localhost:5000/admin/feature_flags -b cookie.txt
```

## OpenAPI & CI Validation
The API specification is served at `/openapi.json`. CI runs a dedicated validation job to ensure spec conformance. You can locally sanity-check it:
```bash
python - <<'PY'
from core.app_factory import create_app
app = create_app({'TESTING': True})
with app.test_client() as c:
    spec = c.get('/openapi.json', headers={'X-User-Role':'admin','X-Tenant-Id':'1'}).get_json()
    from openapi_spec_validator import validate
    validate(spec)
    print('Spec OK with', len(spec.get('paths',{})), 'paths')
PY
```

Use the spec for client generation (e.g. `openapi-generator-cli generate -g typescript-fetch -i openapi.json`).

---
For roadmap and deeper architectural decisions, see `docs/`.

## Auth Quickstart
Short, high-signal overview of the JWT + RBAC model. See `/openapi.json` for schemas & examples (401/403/429).

### Login
POST `/auth/login` with credentials -> returns `access_token` (TTL ~10m) and `refresh_token` (TTL ~14d). Store refresh token securely (never send to frontend JS if you can keep it httpOnly).

### Authorized Request
Send header: `Authorization: Bearer <access_token>`. Missing/invalid -> 401 example: `{"error":"unauthorized","message":"Bearer token missing or invalid"}`.

### Refresh
POST `/auth/refresh` with current refresh token -> new pair (access + refresh). Old refresh becomes invalid (rotation). Re-using a rotated refresh yields 401.

### Logout
POST `/auth/logout` invalidates current refresh token (server forgets its JTI). Access tokens simply expire (short TTL).

### RBAC
Roles: `user` (may only mutate own tasks), `admin` (tenant-wide), `superuser` (cross-tenant, can specify tenant_id on admin endpoints). Attempting forbidden action -> 403 example `{"error":"forbidden","message":"Requires role admin","required_role":"admin"}`.

### Rate Limits (buckets)
| Bucket | Scope | Limit (approx) | Endpoints |
|--------|-------|----------------|-----------|
| `tasks_mutations` | per tenant+user | 60/min | POST/PUT/DELETE `/tasks/*` |
| `feature_flags_admin` | per tenant+user | 20-60/min (op-dependent) | `/features*`, `/admin/feature_flags*` |
429 response example: `{"error":"rate_limited","message":"Too many requests","retry_after":30}` (Retry-After header may be present).

### Error Shapes
Uniform envelope `{error, message}` plus optional fields (e.g. `required_role`, `retry_after`). Always branch on `error`.

### Refresh Rotation Replay Protection
If a refresh token is used once, its JTI in DB is replaced. Re-using the old token later => 401 `unauthorized` (treat as possible replay attempt, trigger re-auth flow).

### CSP Note
Current CSP allows `'unsafe-inline'` temporarily for legacy inline UI snippets. Plan: migrate inline JS/CSS into static assets and remove `'unsafe-inline'` from `script-src` / `style-src` to enable stronger protections.

### References
OpenAPI reusable responses: `Error401`, `Error403`, `Error429`. See `/openapi.json#components/responses/*` for canonical examples.


## License
Proprietary & Confidential. All rights reserved.

---
Generated scaffold intended for iterative build with AI assistance (Copilot). Follow the roadmap phases to implement functionality safely.
