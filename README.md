## Problem Details (RFC7807) — Full Adoption

What
- All endpoints now return RFC7807 Problem Details for error responses (4xx/5xx).

Behavior
- Content type: application/problem+json
- Required fields: type, title, status, detail
- Extensions: request_id (always), incident_id (500), errors[] (422), retry_after (429), required_role (403 when applicable)

Request correlation
- X-Request-Id header is echoed as payload.request_id in problem responses.

Examples
- 401 Unauthorized
  - type: https://example.com/errors/unauthorized
  - title: Unauthorized
  - status: 401
  - detail: unauthorized
  - request_id: 11111111-1111-1111-1111-111111111111
- 422 Validation
  - type: https://example.com/errors/validation_error
  - title: Unprocessable Entity
  - status: 422
  - detail: validation_error
  - errors: [{"field": "name", "message": "required"}]
  - request_id: 22222222-2222-2222-2222-222222222222
- 429 Too Many Requests
  - type: https://example.com/errors/rate_limited
  - title: Too Many Requests
  - status: 429
  - detail: rate_limited
  - retry_after: 30
  - limit: tasks_mutations
  - headers: Retry-After: 30
- 500 Incident
  - type: https://example.com/errors/internal_error
  - title: Internal Server Error
  - status: 500
  - detail: internal_error
  - incident_id: 33333333-3333-3333-3333-333333333333
  - request_id: 33333333-3333-3333-3333-333333333333
# Yuplan Unified Platform (Scaffold)

[![CI](https://github.com/Henkemannn/YuplanUnified/actions/workflows/ci.yml/badge.svg)](https://github.com/Henkemannn/YuplanUnified/actions/workflows/ci.yml)
[![OpenAPI](https://github.com/Henkemannn/YuplanUnified/actions/workflows/openapi.yml/badge.svg)](https://github.com/Henkemannn/YuplanUnified/actions/workflows/openapi.yml)
[![markdownlint](https://github.com/Henkemannn/YuplanUnified/actions/workflows/markdownlint.yml/badge.svg)](https://github.com/Henkemannn/YuplanUnified/actions/workflows/markdownlint.yml)
[![CodeQL](https://github.com/Henkemannn/YuplanUnified/actions/workflows/codeql.yml/badge.svg)](https://github.com/Henkemannn/YuplanUnified/actions/workflows/codeql.yml)
[![API](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Henkemannn/YuplanUnified/master/status/api_status.json)](./)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Henkemannn/YuplanUnified/master/status/coverage-badge.json)](./)
[![GA](https://img.shields.io/badge/GA-v1.0.0-green)](RELEASE_NOTES_v1.0.0.md)

<p align="left">
  <img alt="Ruff" src="https://img.shields.io/badge/Ruff-E,F,I,B,UP,Q-success?logo=python&logoColor=white" />
  <img alt="Mypy" src="https://img.shields.io/badge/Mypy-0%20errors-brightgreen" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-blue" />
</p>

This repository scaffold is the starting point for merging the Municipal (Kommun) and Offshore Yuplan applications into a single multi-tenant, module-driven platform.

## Staging quickstart
- Access and demo guardrails: see `docs/staging-access.md` (simple auth, CSRF, DEMO_UI)
- Smoke run log: see `docs/staging-smoke_2025-11-11.md`
- One-liners (Windows):
  - `make login-ps` (or `pwsh -File scripts/login.ps1`)
  - `make smoke-ps` (or `pwsh -File scripts/smoke.ps1 -BaseUrl https://yuplan-unified-staging.fly.dev -SiteId <SITE_ID> -Week 51`)

## Staging environment (Fly.io)

Current staging URL: https://yuplan-unified-staging-icy-wave-9332.fly.dev/

Landing page `/` links to health (`/health` + `/healthz`), docs (`/docs/`), and the OpenAPI spec (`/openapi.json`).

### Database driver

Staging runs on Postgres (Fly managed cluster) — preferred over SQLite for concurrency & realistic query planning. SQLite is still usable locally and in CI for light tests. Migrations are Alembic-driven; never rely on `create_all` in staging.

### Initialize schema & minimal seed (local dev)

PowerShell (Windows):
```powershell
python tools/init_db.py
```

Bash (macOS/Linux):
```bash
python tools/init_db.py
```

This runs all Alembic migrations (multi-head safe) and seeds tenant `demo` with units `Alpha`, `Bravo`.

### Week view seed example

PowerShell:
```powershell
python tools/seed_weekview.py --tenant demo --year 2025 --week 45 --departments Alpha Bravo
```

Bash:
```bash
python tools/seed_weekview.py --tenant demo --year 2025 --week 45 --departments Alpha Bravo
```

### Postgres staging runbook

See `docs/staging_postgres_runbook.md` for end-to-end commands to:
1. Provision a Fly Postgres cluster
2. Attach and set `DATABASE_URL`
3. Run migrations + seed inside the machine
4. Validate health

If switching to a fresh database or re-running migrations in-place, ensure no conflicting heads (we use `upgrade heads`).


## Contributing
See CONTRIBUTING.md for branching, PR, and quality gates. Use the GitHub Issue templates for GA checklist and roadmap kickoff from the New Issue menu.

## Quick reference (OpenAPI)
* PowerShell helpers: `./scripts/dev.ps1; Invoke-OpenAPIWorkflow` fetches spec, semantic diff, optional spectral lint, focused tests.
* Fetch only: `./scripts/dev.ps1; Get-OpenAPISpec` writes `openapi.json` (badge workflow in CI consumes semantic diff artifacts).
* Local Python fetch (fallback /docs/openapi.json):
  ```
  python fetch_openapi_local.py --base-url http://localhost:5000 --output openapi.json
  ```
* Diff vs baseline manually:
  ```
  python scripts/openapi_diff.py specs/openapi.baseline.json openapi.json --report openapi-diff.txt
  ```
* Breaking changes cause non‑zero exit in diff script; baseline must be updated intentionally in same PR.

## Pre-commit (lokalt)
Kör snabb säkerhetskontroll innan commit:
```bash
pip install pip-audit
pip-audit
```
(*Valfritt:* vi kan lägga till en `.pre-commit-config.yaml` hook senare.)

## Pre-commit
Installera hooks lokalt:
```bash
pip install pre-commit
pre-commit install
```
Kör alla hooks manuellt:
```bash
pre-commit run --all-files
```
Kör pip-audit manuellt (manual stage):
```bash
pre-commit run pip-audit --all-files
```

## Versioning & Release
We follow Semantic Versioning (SemVer):
* MAJOR (`X.y.z`): Any breaking OpenAPI change (as detected by semantic diff rules) or removal of previously documented behavior.
* MINOR (`x.Y.z`): Backwards-compatible additions (new paths/operations/properties/content-types, optional fields, enum expansions).
* PATCH (`x.y.Z`): Bug fixes & non-contract internal changes.

Baseline policy: `specs/openapi.baseline.json` is hard-enforced in CI (must exist – not auto-created). Update it only in the same PR as intentional contract changes. For the beta freeze we will tag the baseline at `v1.0.0-beta`.

Beta readiness checklist: see `docs/v1.0-beta-checklist.md` (all items must be ✅ before cutting the beta tag).

Legend (API diff status): ✅ no breaking · 🟡 additions only · ❌ breaking.

Release workflow: automatically produces OpenAPI diff artifacts (`openapi-diff.txt`, `openapi-diff.json`), a changelog snippet, and a badge snippet. The release action can fall back to generating these live (`force_fallback` input) if artifacts are missing.

After `v1.0.0-beta`: Further additive changes bump MINOR; any breaking change requires a MAJOR plan (`2.0.0`) unless explicitly deferred pre-GA.

For the exact steps, see **[RELEASE_RUNBOOK.md](docs/RELEASE_RUNBOOK.md)**.

### Feature Flag: Strict CSRF
An opt-in stricter CSRF enforcement layer can be enabled with environment variable `YUPLAN_STRICT_CSRF=1`.

When active:
* A per-session token is generated and exposed to templates and JS (meta tag `csrf-token`).
* Mutating requests under selected prefixes (`/diet/`, `/superuser/impersonate/`) MUST include `X-CSRF-Token` header or form field `csrf_token`.
* Failures return RFC7807 problem+json (`csrf_missing` or `csrf_invalid`).
* A lightweight fetch wrapper (`/static/js/http.js`) auto-injects the header in the UI.
* Prefix list expands gradually as tests migrate.

Disable by omitting or setting the variable to `0` (legacy protections remain in place).

### Release helper
PowerShell (Windows):
```powershell
pwsh -File tools/release.ps1 -Kind patch   # or minor / major
```
Make (macOS/Linux):
```bash
make release-patch    # or make release-minor / make release-major
```
This will:
1. Ensure working tree clean
2. Bump version via `tools/bump_version.py`
3. Commit "chore(release): bump version to X.Y.Z"
4. Tag `vX.Y.Z` and push (unless `-NoPush` used in PowerShell)
5. Trigger `.github/workflows/release.yml` which builds the GitHub Release body from notes or template.

## Deprecation policy

We avoid breaking changes. When removal or incompatible changes are required we follow an announce–deprecate–sunset cycle:

### Marking
* HTTP headers on deprecated endpoints:
  * `Deprecation: true` (or an ISO date per RFC 8594)
  * `Sunset: <http-date>` (date support ends)
  * `Link: <https://api.example.com/docs/migrations/XYZ>; rel="sunset"`
* `Warning: 299 api.example.com "Deprecated: will be removed on YYYY-MM-DD"`
* CHANGELOG entry under Unreleased + release notes.
* During deprecation window the API status badge will normally show `changed` (yellow) if additive shims are present.

### Timelines (minimum)
* Response shape additive (new optional fields): no grace needed.
* Field removals: ≥ 90 days.
* Endpoint removal / contract-breaking change: ≥ 180 days.

### Communication
* Versioned docs page with migration examples.
* For enterprise / partners: outbound email (contact list) at announce + 30d before sunset.

### Versioning
* If an immediate incompatible change is unavoidable: bump MAJOR and/or ship a new path or versioned media type; prefer feature flag–guarded behavior until consumers migrate.

---

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
1. Create virtualenv & install deps (or use `make install` / `Install-Deps`):
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
  # or
  make dev
  # or PowerShell
  ./scripts/dev.ps1; Start-App
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

### Rapport – Exportera PDF (Pass D)
Klientside-PDF via webbläsarens print-funktion. Ingen serverändring krävs och CSP-respekteras.

- UI: Knapp “Export PDF” i Rapport-panelen (disabled tills data finns via “Läs in”).
- Funktion: `exportReportPdf(reportJson, week)` bygger en print-vy (rubrik, tabell, summering) och anropar `window.print()`.
- CSS: `@media print` sätter A4, 12mm marginaler, döljer header/meny/knappar och justerar rutnätskort.
- Tillgänglighet: Fokus återställs till knappen efter utskrift.

Manuell verifikation:
1) Öppna “Rapport”, välj vecka och klicka “Läs in”.
2) Klicka “Export PDF” → Förhandsgranskning visar rubrik, tabell och totals. Avbryt/Skriv ut enligt behov.

#### Feature Flag: `rate_limit_export`
The export endpoints have an optional opt-in rate limit controlled per tenant via the `rate_limit_export` feature flag.

Default: OFF (no rate limiting applied).

When ON for a tenant:
* Limit: 5 requests per rolling fixed window of 60 seconds per `(tenant_id:user_id)` bucket.
* Token Bucket: Export endpoints are configured with token bucket defaults (burst = quota) via `FEATURE_LIMITS_DEFAULTS_JSON`; fairness on bursts while preserving same average rate.
#### Feature Flag: `rate_limit_admin_limits_write`
Controls optional rate limiting of admin limit mutation endpoints (`POST /admin/limits`, `DELETE /admin/limits`).

Default: OFF (no throttling). When enabled for a tenant:
* Default quota: 10 requests per 60s window (registry key `admin_limits_write`).
* Per-tenant override supported via `FEATURE_LIMITS_JSON` using key `tenant:<id>:admin_limits_write`.
* Registry global override via `FEATURE_LIMITS_DEFAULTS_JSON` key `admin_limits_write`.
* Exceeding quota yields HTTP 429 ProblemDetails (application/problem+json) with fields: status=429, type=/rate_limited, retry_after, limit and header Retry-After.
* Metrics emitted: `rate_limit.hit` (tags: name=admin_limits_write, outcome=allow|block, window=60) and `rate_limit.lookup` (source=fallback|default|tenant).

Enable for a pilot tenant via:
```
POST /admin/feature_flags
{"name": "rate_limit_admin_limits_write", "enabled": true}
```

* Exceeding the quota results in HTTP 429 ProblemDetails and header `Retry-After: <seconds>`.

Enable via Admin API (role editor/admin allowed to manage flags):
```
POST /admin/feature_flags
{"name": "rate_limit_export", "enabled": true}
```
Disable:
```
POST /admin/feature_flags
{"name": "rate_limit_export", "enabled": false}
```
Operational Guidance:
1. Turn flag ON for a pilot tenant; observe `rate_limit.hit` metrics (tags: name, outcome, window).
2. Adjust quota in code if needed (central decorator parameter) before broad enablement.
3. Keep flag OFF for high-volume reporting tenants until validated.

### Token Bucket (fair limits, burst support)

Utöver fixed window stöds token bucket per limit via registry:

- `quota`: målhastighet (tokens per `per_seconds`)
- `per_seconds`: påfyllningsintervall
- `burst` (valfritt): kapacitet; default = `quota`
- `strategy`: `"token_bucket"` eller `"fixed"` (default via env/global)

Exempel (defaults via env):
```json
FEATURE_LIMITS_DEFAULTS_JSON='{
  "export_csv": {"quota": 5, "per_seconds": 60, "burst": 5, "strategy": "token_bucket"}
}'
```

#### Retry-After semantik

Svar vid block inkluderar header `Retry-After` och JSON-fält `retry_after`.

Precision: heltal i sekunder, avrundat uppåt (ceil). Minst 1.

Gäller både fixed och token_bucket.

#### Metrics

`rate_limit.lookup` taggar: `name`, `source=tenant|default|fallback`, `strategy=fixed|token_bucket`

`rate_limit.hit` taggar: `name`, `outcome=allow|block`, `window` (sekunder), `strategy`.

#### Redis-backend

Token bucket finns för memory (test/dev) och Redis (prod).

Tester för Redis skip:ar automatiskt om Redis inte är tillgängligt.

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
See also consumer integration guidance in `docs/CONSUMERS.md` and the developer convenience targets below.
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

## 🧱 Infra

### Branch protection
Regler för `master` versioneras i `infra/bp.json`. Detta är source of truth för vilka status‑checks och skydd som gäller.

### Sync
Kör `tools/sync_branch_protection.py` eller följ instruktionerna i `docs/branch-protection.md` för att tillämpa reglerna via GitHub‑API.

## Architecture Decisions

## Staging deploy (v0.4)

This release adds a containerized runtime and a simple health endpoint to make the app easy to deploy to a staging environment.

Included:
- Dockerfile (Python slim, non-root) running `gunicorn core.app_factory:create_app()` on port 8080
- `gunicorn.conf.py` (timeout=60, loglevel=info)
- Health endpoint at `GET /healthz` returning `{ "status": "ok" }`
- `.env.example` with common variables
- Optional tools: `tools/init_db.py` (alembic + minimal seed), `tools/seed_weekview.py` (dev-only weekview seed)
- Fly.io manifest `fly.toml` (you can alternatively use Render with the same Dockerfile)

### Environment variables

Copy `.env.example` and set the following (names mirror staging defaults):

- DATABASE_URL (e.g. `postgresql+psycopg://user:pass@host:5432/yuplan`)
- SECRET_KEY (any random string for session signing)
- FF_WEEKVIEW_ENABLED=true
- FF_REPORT_ENABLED=true
- FF_ADMIN_ENABLED=false

Feature flags default here are for convenience; per-tenant DB overrides take precedence.

### Deploy on Fly.io

Prerequisites:
- Fly CLI installed and authenticated
- A Postgres instance (Fly Postgres or external)

Steps:

```powershell
fly launch --no-deploy
# Set secrets (examples):
fly secrets set DATABASE_URL="postgresql+psycopg://user:pass@host:5432/yuplan" SECRET_KEY="change-me"
# Deploy
fly deploy
```

Health check: `GET /healthz` → 200 with `{ "status": "ok" }`.

### Optional: Render

If deploying on Render instead, use the Dockerfile, set the Health Check Path to `/healthz`, and configure environment variables from `.env.example`.

### Database init (optional)

Run Alembic and seed minimal data:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://user:pass@host:5432/yuplan"
python tools/init_db.py
```

Dev-only seed example for weekview data:

```powershell
$env:DATABASE_URL = "sqlite:///unified.db"  # or Postgres URL
python tools/seed_weekview.py --year 2025 --week 45
```

### Smoke tests

After deploy, validate the following:

- GET `/healthz` → 200
- GET `/api/weekview?...` → 200 + ETag
- PATCH `/api/weekview` with If-Match → 200 + new ETag
- GET `/api/weekview` with If-None-Match → 304
- GET `/api/report?...` → 200 + ETag
- GET `/api/report/export?...&format=csv|xlsx` → 200 + file

- See ADR index: `adr/README.md`

Current ADRs:
- ADR-001: Global 429 Standardization — `adr/ADR-001-global-429-standardization.md`
- ADR-002: Strict CSRF Rollout — `adr/ADR-002-strict-csrf-rollout.md`
- ADR-003: Full RFC7807 Adoption and Legacy Error Retirement — `adr/ADR-003-full-rfc7807-adoption.md`

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
| Fetch OpenAPI (Makefile) | `make openapi` |
| Smoke test menu import | `make smoke` |
| Full local CI pass | `make ci` |
| Release readiness | `make ready` |

### Makefile & PowerShell Helpers
For POSIX systems a `Makefile` provides shortcuts: `make install dev test lint openapi smoke ci`.

For Windows PowerShell use the script `scripts/dev.ps1`:
```
./scripts/dev.ps1; Install-Deps; Start-App
./scripts/dev.ps1; Lint-App; Test-App
./scripts/dev.ps1; Fetch-OpenAPI; Smoke
./scripts/dev.ps1; python scripts/check_release_ready.py  # release readiness
```

### API Consumers Guide
Client developers should start with `docs/CONSUMERS.md` (base URL, auth, error model, rate limit handling, contract stability rules, example import flow).

### Contributing

Ruff körs inte på Markdown-filer. För dokumentationslint använder vi markdownlint (se `.markdownlint.json` och GitHub Action `markdownlint`).

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

### Release Readiness (Local Gate)
Before tagging a beta/GA release run:
```
make openapi   # ensure fresh spec
make ready     # format+lint+tests+spectral (if installed)+semantic diff+checklist
```
The script fails fast if baseline missing, breaking diff detected, or checklist has open items.

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

Pocket 4 (API handlers):
 - `core.api_types` (central TypedDict contracts, NewType IDs)
 - `core.admin_api`
 - `core.diet_api`
 - `core.service_metrics_api`
 - `core.service_recommendation_api`
 - Unified ok/error envelope (`{"ok": False, "error": code, "message"?: str}`) applied consistently.
 
 Pocket 5 (current): Tasks API + new tasks service (strict) – adds Task* contracts, unified error envelope (`ok: False` on errors).

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
- rate_limit_admin_limits_write (flag-gated admin limits write throttle)
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

The OpenAPI spec is generated in `core/app_factory.py` and can merge modular parts:

Environment toggle:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAPI_INCLUDE_PARTS` | `true` | When truthy merges `openapi/parts/admin.yml` (and future parts) into `/openapi.json`. Set to `0`/`false`/`no` to disable. |

Admin endpoints and schemas live in `openapi/parts/admin.yml` and are automatically merged unless disabled.
See docs/ for full architecture, data model, migration plan, module definitions, roadmap, deployment guidance.

### OpenAPI Baseline & Semantic Diff
To guard against accidental breaking API changes, CI enforces a committed baseline at `specs/openapi.baseline.json` (HARD policy – build fails if missing) and performs a semantic diff:

Rules treated as breaking (CI fail):
* Removing a path
* Removing an operation (method) from an existing path
* Removing a response status code for an operation
* Removing a request body or narrowing its content-types
* Removing a response content-type
* Schema changes that remove properties, remove enum values, add new required properties, change `$ref`, change type

Additions (new paths, operations, responses, request bodies) are allowed and reported as non-breaking.

Workflow behavior:
* Step normalizes current spec (sorted JSON) then compares to baseline via `scripts/openapi_diff.py`.
* Missing baseline now fails the workflow (no silent auto-create). This prevents accidental drift being “blessed” implicitly.
* Subsequent breaking diffs cause exit code 1 and fail the job.

Breakage rules (treated as breaking and fail the job):

* Removal of paths, operations, responses, request bodies
* Removal of response or request content-types (content-type narrowing)
* Enum value removals
* Property removals or new required properties
* Type or $ref changes
* `format` changes (any change, considered narrowing)
* Array: `minItems` increase, `maxItems` decrease
* String: introduction or increase of `minLength`, decrease or introduction of `maxLength`, addition or change of `pattern`

Widenings allowed (examples): removing `pattern`, increasing `maxLength`, decreasing `minLength`, adding new optional properties, adding enum values, adding new paths/operations/responses/content-types.

## 🔐 Confidentiality Notice
Yuplan är proprietär mjukvara. © 2025 Henrik Jonsson — All Rights Reserved.
All kod, dokumentation och data tillhör Henrik Jonsson. Obehörig användning är förbjuden.

## Strict typing pockets (RC1)

The goal for RC1 is to keep noise low while ensuring core reliability. “Strict: Yes” means `mypy --strict` (or equivalent config) passes for that module; “No” means temporarily relaxed while we iterate.

| Module                       | Strict | Notes                                                     |
|-----------------------------|:------:|-----------------------------------------------------------|
| `core.errors`               |  Yes   | Central error types and helpers.                          |
| `core.http_errors`          |  Yes   | RFC7807 mapping; kept small and well-typed.               |
| `core.csrf`                 |  Yes   | Token utilities; decorator noise silenced as needed.      |
| `core.app_factory`          |  Yes   | Return types for app/blueprints typed.                    |
| `core.rate_limit`           |  Yes   | Public API typed; helpers annotated.                      |
| `core.limit_registry`       |  Yes   | Registry generics constrained.                            |
| `core.audit_events`         |  Yes   | Event dataclasses/TypedDicts locked down.                 |
| `core.audit_repo`           |  Yes   | Narrow I/O surface; typed repository methods.             |
| `core.jwt_utils`            |  Yes   | (From earlier pocket)                                     |
| `core.db`                   |  Yes   | (From earlier pocket)                                     |
| `core.*_api`                |   No   | RC1 noise bucket—gradual re-enable post-RC.               |
| `core.ui_blueprint`         |   No   | DTO/view-model churn; enable after endpoints stabilize.   |
| `legacy/*`                  |   No   | Excluded in RC1.                                          |
| `importers/*`               |   No   | Deferred; high change rate.                               |
| `telemetry/*`               |   No   | Deferred; pending event schema freeze.                    |

Re-enable plan (post-RC): reintroduce modules one at a time; prefer `TypedDict`/`Protocol` facades over deep refactors; keep diffs small.

Updating the baseline intentionally:
1. Implement your API change and update spec generation.
2. Regenerate spec locally:
  ```bash
  curl -fsS http://127.0.0.1:5000/openapi.json | jq -S . > specs/openapi.baseline.json
  ```
  (Without `jq` you can pretty-print using Python: `python -c "import json,sys;import urllib.request as u;spec=json.load(u.urlopen('http://127.0.0.1:5000/openapi.json'));open('specs/openapi.baseline.json','w',encoding='utf-8').write(json.dumps(spec,sort_keys=True,ensure_ascii=False,indent=2))"`)
3. Commit the updated baseline in the same PR as the change with a clear message (e.g. `chore(openapi): update baseline for new /foo endpoints`). Provide a brief rationale if any breaking flags were accepted (rare – implies version negotiation or major bump).

**Artifacts:** CI laddar upp både en mänskligt läsbar diff (`openapi-diff.txt`) och en maskinläsbar JSON (`openapi-diff.json`). Den senare kan användas av PR-botar eller dashboards för att automatiskt kommentera breaking/additive förändringar.

**PR Labels:** Pull Requests får automatiskt label `api:breaking` vid breaking ändringar eller `api:changed` vid enbart additions. Stabil diff (`ok` utan additions) ger ingen `api:*` label alls (renare label-lista).

**Legend:** ✅ no breaking · 🟡 additions only · ❌ breaking

**Release-hjälp:** CI producerar ytterligare artefakter:
* `openapi-extras/openapi-changelog.md` – färdig sektion att klistra in högst upp i `CHANGELOG.md` vid release.
* `openapi-extras/api-badge.md` – en badge-rad som kan läggas till i README eller PR-beskrivning för att signalera aktuell API-status.

Semantic diff script location: `scripts/openapi_diff.py` (pure stdlib, no dependencies). Extend it for deeper checks (e.g. minItems tightening) if needed.


## Error Model
## Error model (RFC 7807)

In parallel with the compact legacy envelope we support (and will migrate fully to) RFC 7807 problem details using media type `application/problem+json`.

Fields:
- `type` (string, URI) – Stable identifier for the problem category.
- `title` (string) – Short, human stable headline.
- `status` (number) – HTTP status code.
- `detail` (string) – Human-readable description of this specific occurrence.
- `instance` (string, URI, optional) – Correlates this occurrence (mirrors `request_id`).
- `errors` (object, optional) – Field specific validation errors: `{ "field": ["msg1", "msg2"] }`.

Problem type registry (initial set):

| type | title | http status | when used |
|------|-------|------------:|-----------|
| `about:blank` | Standard HTTP error | varies | Fallback
| `https://api.example.com/problems/validation` | Validation failed | 400 / 422 | Invalid payload / parameter
| `https://api.example.com/problems/unauthorized` | Unauthorized | 401 | Missing / bad token
| `https://api.example.com/problems/forbidden` | Forbidden | 403 | Lacking permission / role
| `https://api.example.com/problems/not-found` | Resource not found | 404 | Entity missing
| `https://api.example.com/problems/unsupported-media-type` | Unsupported media type | 415 | Wrong `Content-Type`
| `https://api.example.com/problems/rate-limited` | Rate limit exceeded | 429 | Too many requests
| `https://api.example.com/problems/internal` | Internal error | 500 | Unexpected error

HTTP Headers:
* Always: `Content-Type: application/problem+json`
* On 429: include `Retry-After` + any relevant `X-RateLimit-*` headers.

Examples:

Validation (422):
```json
{
  "type": "https://api.example.com/problems/validation",
  "title": "Validation failed",
  "status": 422,
  "detail": "title must not be empty",
  "errors": {"title": ["must not be empty", "min length is 1"]}
}
```
Unsupported media (415):
```json
{
  "type": "https://api.example.com/problems/unsupported-media-type",
  "title": "Unsupported media type",
  "status": 415,
  "detail": "Expected Content-Type application/json"
}
```
Rate limited (429):
```json
{
  "type": "https://api.example.com/problems/rate-limited",
  "title": "Rate limit exceeded",
  "status": 429,
  "detail": "Try again later"
}
```

Implementation notes:
* `title` derived from the registered problem type (not user input).
* `detail` is request-specific and safe to show to end user (no stack traces / secrets).
* `instance` should correlate with logs (`request_id`) for support.

See also: `docs/problems.md` for the full problem type catalog with examples and client handling tips.

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

## Pagination
List endpoints now return a unified pagination envelope:

```jsonc
{
  "ok": true,
  "items": [...],
  "meta": { "page": 1, "size": 20, "total": 137, "pages": 7 }
}
```

Query params:
| Name | Default | Min | Max | Notes |
|------|---------|-----|-----|-------|
| `page` | 1 | 1 | - | 1-based index |
| `size` | 20 | 1 | 100 | >100 is clamped to 100 |
| `sort` | (none) | - | - | Reserved for future field sorting |
| `order` | `asc` | - | - | `asc`/`desc`; ignored until `sort` is enabled |

Stable ordering (current implementation) uses `created_at DESC, id DESC` internally to avoid duplication or gaps when new rows arrive between pages. Invalid numeric inputs produce a `400` error envelope (`{"ok": false, "error": "bad_request", ...}`). Invalid `order` values fallback to `asc`.

Future extensions may add cursor-based pagination once datasets grow large; current offset approach is sufficient for MVP scale.

Deprecation (alias keys): Responses still include legacy `notes` / `tasks` top-level arrays for backward compatibility, but these are marked with deprecation headers (`Deprecation: true`, `Sunset: Wed, 01 Jan 2026 00:00:00 GMT`). Clients should migrate to `items` before the sunset date.

Centralization (2025-10-02): Deprecation headers are now applied via `core.deprecation.apply_deprecation`, which sets RFC 8594-compliant `Deprecation`, `Sunset`, `Link` (rel="deprecation") plus an explicit `X-Deprecated-Alias` header enumerating emitted legacy keys. A telemetry metric `deprecation.alias.emitted` (tags: `endpoint`, `aliases`) is incremented to track client migration velocity. Removing aliases after the sunset simply becomes a one-line change (stop passing alias list) with observability to ensure low residual usage first.

## Rate-limit registry (per tenant)

Yuplan kan läsa kvotinställningar per **tenant** och **limit-namn** från konfig.
Resolution order:
1) Tenant override: `FEATURE_LIMITS_JSON` nycklar `tenant:<id>:<name>`
2) Globala defaults: `FEATURE_LIMITS_DEFAULTS_JSON` nycklar `<name>`
3) Safe fallback: `quota=5`, `per_seconds=60`

**Schema (JSON):**
- `quota` (int ≥ 1)
- `per_seconds` (int 1–86400)

**Exempel**
```json
FEATURE_LIMITS_JSON='{
  "tenant:42:export_csv": {"quota": 10, "per_seconds": 60}
}'
FEATURE_LIMITS_DEFAULTS_JSON='{
  "export_csv": {"quota": 5, "per_seconds": 60}
}'
```

**Användning i kod**
Dekoratorn hämtar registry-värden när quota/per_seconds inte anges:

```python
@limit(name="export_csv", key_func=user_bucket, feature_flag="rate_limit_export", use_registry=True)
def export_notes_csv(): ...
```

**Telemetri**
Varje uppslag skickar `rate_limit.lookup` med taggen `source=tenant|default|fallback`.

### Admin inspection endpoint `/admin/limits`

Ger insyn i effektiva gränser.

Query-parametrar:
- `tenant_id` (int, optional): Om satt returneras union av globala defaults och tenant overrides. Utan `tenant_id` visas endast globala defaults.
- `name` (str, optional): Filtrerar till ett specifikt limit-namn. Om kombinerat med `tenant_id` och namnet saknas i både overrides och defaults exponeras en rad med `source=fallback` (för att visa vilken fallback som skulle gälla). Utan träff och utan `tenant_id` returneras tom lista (fallback brus filtreras bort).
- `page`, `size`: Standardpaginering.

Svar:
```jsonc
{
  "ok": true,
  "items": [ { "name": "export_csv", "quota": 5, "per_seconds": 60, "source": "default" } ],
  "meta": { "page": 1, "size": 20, "total": 1, "pages": 1 }
}
```

`source` värden:
- `tenant`: Explicit override för given tenant
- `default`: Global default
- `fallback`: Safe baseline (visas endast vid explicit name-filter + tenant_id när inga andra träffar finns)

Användningsfall: felsöka oväntade 429-svar, verifiera rollout av nya limits, samt revision av overrides.

### Audit Persistence & Listing

Audit-händelser skrivs persistenta i tabellen `audit_events` via `core.audit.log_event` (kallas av admin-limit write endpoints m.fl.).

Minimalt fältset per event:
| Field | Typ | Beskrivning |
|-------|-----|-------------|
| ts | datetime (UTC) | Tidsstämpel för event (servergenererad). |
| tenant_id | int? | Tillhörande tenant (kan vara null för globala händelser). |
| actor_user_id | int? | Användar-id (om session finns). |
| actor_role | str | Normaliserad roll (admin, viewer, etc). |
| event | str | Event-nyckel (t.ex. `limits_upsert`). |
| payload | object? | Godtycklig JSON (limit_name, quota, diffs etc). |
| request_id | str? | Korrelations-id (kopplas även till structured log). |

Endpoint (admin-roll krävs):
```
GET /admin/audit
```
Query-parametrar (alla optional):
| Param | Typ | Default | Notering |
|-------|-----|---------|----------|
| tenant_id | int | - | Filtrera på tenant. |
| event | string | - | Filtrera exakt event-namn. |
| from | RFC3339 datetime | - | Inklusiv nedre gräns (ts >= from). |
| to | RFC3339 datetime | - | Inklusiv övre gräns (ts <= to). |
| q | string | - | Case-insensitive partial match mot serialiserat payload. |
| page | int | 1 | Standardpaginering. |
| size | int | 20 | Max 100 (clamp). |

Svar (PageResponse<AuditView>):
```jsonc
{
  "ok": true,
  "items": [
    { "id": 12, "ts": "2025-10-05T12:02:00Z", "tenant_id": 5, "actor_role": "admin", "event": "limits_upsert", "payload": {"limit_name": "exp", "quota": 9}, "request_id": "..." }
  ],
  "meta": { "page": 1, "size": 20, "total": 137, "pages": 7 }
}
```
Headers: `X-Request-Id` (echo eller genererad) för log-korrelation.

Retention:
* Konfig via env `AUDIT_RETENTION_DAYS` (default 90) – purge-funktion finns i `AuditRepo.purge_older_than(days)` (schemalägg extern körning/cron).
* Indexering: `(tenant_id, ts)` och `(event, ts)` för filter + tidsintervall.

Structured Logging:
* Varje HTTP-respons loggas med JSON-linje: `{request_id, tenant_id, user_id, method, path, status, duration_ms}`.
* `request_id` kopplas till audit events för end-to-end spårbarhet.

Exempel flow:
1. Admin gör `POST /admin/limits` → audit event `limits_upsert` skrivs.
2. `GET /admin/audit?event=limits_upsert` listar händelsen.
3. Support använder `X-Request-Id` för att hitta motsvarande access-logg.

Observability:
* Eventvolym och retention övervakas separat (TODO: framtida metrics `audit.insert.count`).
* Fel vid skrivning fångas tyst (audit ska ej stoppa primär kodväg) – logga separat i framtida hårdare läge.

### Operations: Audit Retention CLI

Ett enkelt skript för att manuellt eller via cron städa gamla audit events.

Körning:
```
python scripts/audit_retention_cleanup.py --days 90 --dry-run
python scripts/audit_retention_cleanup.py --days 90
```

Argument:
| Flag | Beskrivning |
|------|-------------|
| `--days <int>` | Retention-fönster i dagar (default `AUDIT_RETENTION_DAYS` eller 90). |
| `--dry-run` | Räknar kandidater utan att radera. |

Output exempel:
```
[DRY-RUN] would delete 42 audit events older than 2025-07-07T12:34:56.123456+00:00
deleted 42 audit events older than 2025-07-07T12:34:56.123456+00:00
```

Exit codes:
| Kod | Betydelse |
|-----|-----------|
| 0 | OK / lyckad körning |
| 1 | Oväntat fel (exception) |
| 2 | Ogiltigt argument (t.ex. `--days < 1`) |

Cron-exempel (daglig 02:15 UTC):
```
15 2 * * * /usr/bin/python /opt/app/scripts/audit_retention_cleanup.py --days 90 >> /var/log/app/audit_retention.log 2>&1
```

Rekommendation: Kör med `--dry-run` först i staging och kontrollera volym innan första riktiga purge i prod.


### Admin write endpoints (overrides)

Skapa/uppdatera eller ta bort tenant-specifika overrides:

| Method | Path | Body | Effekt |
|--------|------|------|--------|
| POST | `/admin/limits` | `{tenant_id,name,quota,per_seconds}` | Upsert override (clamp: quota≥1, 1≤per_seconds≤86400) |
| DELETE | `/admin/limits` | `{tenant_id,name}` | Idempotent borttagning av override |

Svar (POST):
```jsonc
{ "ok": true, "item": {"tenant_id": 7, "name": "export_csv", "quota": 12, "per_seconds": 60, "source": "tenant"}, "updated": true }
```

Svar (DELETE):
```jsonc
{ "ok": true, "removed": true }
```

Validering returnerar `400` vid saknade fält eller ogiltiga tal. Idempotent delete (`removed=false` när override saknas). Endast `admin` (eller `superuser` om roller utökas) har rättighet.

## Import API
Three editor/admin protected endpoints allow structured ingestion of task-like rows:

| Method | Path | Format | Notes |
|--------|------|--------|-------|
| POST | `/import/csv` | CSV | Always available. Validates header row must contain `title,description,priority`. Returns 415 if file extension/MIME not clearly CSV. |
| POST | `/import/docx` | DOCX table | Optional (python-docx). 415 Unsupported if library absent. First table only; header row inferred from first table row. |
| POST | `/import/xlsx` | XLSX sheet | Optional (openpyxl). 415 Unsupported if library absent. First worksheet only. |

Response on success:
```jsonc
{
  "ok": true,
  "rows": [ { "title": "A", "description": "Alpha", "priority": 1 } ],
  "meta": { "count": 1 }
}
```

Error envelope examples:
```jsonc
// Unsupported format (e.g. DOCX not installed)
{ "ok": false, "error": "unsupported", "message": "docx import not available" }
// Validation failure (missing required column)
{ "ok": false, "error": "invalid", "message": "Missing required column priority" }
// Rate limited (flag enabled + quota exceeded)
{ "ok": false, "error": "rate_limited", "message": "Too many requests" }
```

Rate Limiting (opt-in): set `FEATURE_FLAGS.rate_limit_import = true` (test config) to enforce a fixed 60s window (5/min when forced via `X-Force-Rate-Limit` headers in tests). Absent flag => unlimited.

OpenAPI schemas: `ImportRow`, `ImportOkResponse`, `ImportErrorResponse` with `error` enum: `invalid | unsupported | rate_limited`.

Implementation Notes:
1. CSV path performs lightweight extension/MIME gating (future: sniff magic bytes for stronger validation).
2. Optional DOCX/XLSX parsers are wrapped in try/except at import time; endpoints short-circuit with 415 when unavailable.
3. Validation + normalization centralized in `core/importers/validate.py` (raises `ImportValidationError`).
4. Strict typing enforced via pocket entry `[mypy-core.import_api] strict = True`.

Future Enhancements:
* Per-tenant import quotas (flag & DB overrides similar to export limits).
* Row-level error reporting array (currently aggregated in exception message for brevity).
* Streaming large file parsing (chunked CSV reader) once >5MB cap is revisited.


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
\n+## Metrics (Lightweight Instrumentation)
The platform includes a minimal metrics abstraction (`core.metrics`) with a noop default and an optional logging backend.

Activate logging backend (emits INFO lines via logger `metrics`):
```
set METRICS_BACKEND=log  # Windows PowerShell: $env:METRICS_BACKEND="log"
python run.py
```

Example log line when a legacy cook creates a task (fallback path):
```
metric name=tasks.create.legacy_cook tags={'tenant_id': '1', 'user_id': '1', 'role': 'cook', 'canonical': 'viewer'}
```

Backend selection:
- noop (default) — no overhead.
- log — structured-ish single line per increment, safe for dev / staging.

Custom backends can be added by implementing the `Metrics` protocol and calling `set_metrics()` during app startup.

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

Add a section linking to the idea bank
💡 New Ideas

Concept sketches and early features are kept in new_ideas/
.

## Secrets & privacy

### Superuser password (local/CI)
The script `scripts/set_superuser.py` no longer contains a hardcoded password. It requires the environment variable `YUPLAN_SUPERUSER_PASSWORD` to be set.

- Local (PowerShell):
  - `$env:YUPLAN_SUPERUSER_PASSWORD = "<strong password>"`
  - `python scripts/set_superuser.py`

- CI (GitHub Actions):
  - Add a repository secret named `YUPLAN_SUPERUSER_PASSWORD` and expose it to jobs that need to seed the superuser.
  - Example step:
    - `env: { YUPLAN_SUPERUSER_PASSWORD: ${{ secrets.YUPLAN_SUPERUSER_PASSWORD }} }`

Important: Never commit secrets. `.gitignore` already ignores `.env*`, `secrets.*`, and `credentials.*` files.

<!-- doc lint rerun 2 -->

