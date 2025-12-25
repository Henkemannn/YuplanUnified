## [0.3.2] - 2025-11-13 (Hotfix: menu-choice + requirements cleanup)

### Hotfix
- Fix 500 error on PUT `/menu-choice` under SQLAlchemy 2.x by wrapping raw `SELECT` in `sqlalchemy.text()` (concurrency + idempotence tests all passing).

### Tooling
- Cleaned `requirements.txt` (removed stray branch markers / duplicate pins, kept `gunicorn==22.0.0`, restored `PyYAML>=6.0`) ensuring stable installs and green strict pockets (mypy) workflow.

### Quality
- Test suite: 353 passed, 7 skipped (menu-choice focused tests: 7/7).

---
## [0.3.0] - 2025-11-13 (Branding, Installability, Menyval, CSV Preview)

### Added
- Branding & PWA: `manifest.webmanifest`, favicon, apple-touch, and icon set wired into templates with cache-busting.
- Static assets reliability: explicit Flask routes for `/manifest.webmanifest` and `/favicon.ico` with correct MIME; Safari pinned tab; optional WhiteNoise WSGI static fallback.
- Pass B – Menyval: Client demo + focused smoke covering idempotence, mutation, weekend rule (422), and ETag 304 behavior.
- Pass C – Report CSV export: Client-side CSV export with BOM and stable column layout; basic totals fallback.
- Pass D – PDF print: Client-side print view using existing styles; quick one-click export.
- Pass F – Admin CSV import (preview): Client-side parser (BOM stripping, delimiter autodetect, quoted fields), column mapping UI, preview table, and summary; unit tests with ÅÄÖ and escaping.

### Changed
- Demo HTML and JS wired to new branding assets; consolidated demo navigation; improved ARIA attributes and focus handling.
- Smoke scripts updated to include CSRF on write requests and avoid false negatives with conditional requests.

### Ops
- Fly staging deploy recipe; staging smoke checklist green (root, /demo, manifest, favicon, icon, menu-choice).
- Feature flag `csv_import_preview` added (environment-driven). Default OFF in production, ON in staging. The CSV import preview section is gated in `templates/demo_admin.html`.

---

## [Unreleased]
- Pilot scope clarification: Auth endpoints remain on legacy envelopes during the ProblemDetails pilot. Migration to ProblemDetails for auth will occur in a later sweep once clients/tests are updated.
- Legacy 429 responses now include `retry_after` (JSON) and `Retry-After` (header), and when available a `limit` field indicating the symbolic rate limit name. This applies to non-pilot endpoints; pilot endpoints continue to emit RFC7807 with `retry_after`.
 - Docs: Add Global 429 Standardization guide (`docs/429-standardization.md`).
 - Docs: Add ADR-002 Strict CSRF Rollout (`adr/ADR-002-strict-csrf-rollout.md`).
 - Docs: Add ADR-003 Full RFC7807 Adoption (`adr/ADR-003-full-rfc7807-adoption.md`).

### Added
- RFC7807 ProblemDetails pilot (flag `YUPLAN_PROBLEM_ONLY=1` by default)

### Changed
- Non-pilot 403 legacy envelopes now include `required_role` consistently

### Docs
- README and SECURITY updated with pilot scope, examples, and rollout plan

### CI
- Gate ensuring pilot endpoints emit `application/problem+json` when flag enabled
## Unreleased

- Weekly Report – Export Phase 2 (Excel)
	- Adds an “Exportera Excel” action on the weekly report view
	- New route `/ui/reports/weekly.xlsx` exporting coverage data for a given `site_id`/`year`/`week` as `.xlsx`
	- Uses the same coverage data source as the HTML weekly report and the CSV export
	- Covered by `tests/ui/test_unified_report_weekly_export_excel_phase2.py`

- Weekly Report – Export Phase 3 (PDF)
	- Adds an “Exportera PDF” action to the weekly report view
	- New route `/ui/reports/weekly.pdf` returning a print-friendly PDF using the unified weekly print template
	- Uses the same coverage data as the HTML/CSV/Excel reports
	- Covered by `tests/ui/test_unified_report_weekly_export_pdf_phase3.py`

### Added
- Unified Portal – Department Week View (Phase 2 UI)
	- New `templates/unified_portal_week.html` template wired to existing vm/route
	- Unified design tokens, responsive 1/2/3 column layout
	- Accessibility improvements (role/button/tabindex/aria-label)
	- Resilient scroll-to-today and keyboard interactions
	- Added `docs/portal_department_week.md` and screenshot placeholders
	- Phase 2 UI test suite (subset 58/58 passed)

- Unified Portal – Department Week View (Phase 3 navigation)
	- Meal blocks now navigate to `/ui/planera/day` using existing route and vm data
	- No backend/API changes; target route remains behind `ff.planera.enabled`
	- Navigation implemented via `openMealDetails(dayKey, mealType)` in `static/unified_portal.js`
	- UI tests extended in `tests/ui/test_portal_department_week_ui_phase3.py` (subset 59/59 passed)

### Features
- feat(core): RFC7807 full adoption — all endpoints return ProblemDetails. Standardized 429 includes `Retry-After` header and `retry_after` body field; 401/403 carry appropriate details, 422 includes `errors[]`, and 500 emits `incident_id`.

### Maintenance
- Legacy `templates/portal_week.html` retired. Both `/portal/week` (legacy path) and `/ui/portal/week` (enhetsportal) now render `templates/unified_portal_week.html`, with behavior controlled by VM flags (e.g., `force_show_dinner`).


### Added
- **Optimistic Concurrency Control**: ETag/If-Match support for `/admin/users`, `/admin/roles`, and `/admin/feature-flags` endpoints
  - DELETE operations require `If-Match` header (strict) - returns 400 if missing, 412 if mismatch
  - PATCH/PUT operations allow operation without `If-Match` (lenient) - returns 412 if provided but mismatched
  - ETag response headers included in successful PATCH/PUT responses
  - Typed RFC7807 ProblemDetails responses for 412 Precondition Failed and 400 Bad Request
  - New `core.concurrency` module with strict mypy typing
  - Documentation in `docs/optimistic-concurrency.md`
  - Comprehensive test coverage in `tests/admin/test_admin_etag_concurrency.py`
- Strict Pocket 5: Tasks API & service under `--strict`.
- Unified error envelope repo-brett: `{ "ok": false, "error", "message?" }`.
- Tasks: `PATCH /tasks/{id}` (behåller `PUT` tills vidare).
- Full OpenAPI spec restored (`/openapi.json`) covering features, notes, tasks & admin feature flags + validation test (`tests/test_openapi_full.py`).
- Metrics: `tasks.create.legacy_cook` instrumentation (no-op backend by default) capturing tenant_id/user_id/role/canonical.
- Metrics: Logging backend (`METRICS_BACKEND=log`) enabling INFO-level emission of metric increments.
 - Plan: Legacy cook task creation fallback slated for deprecation (observation phase active; see DECISIONS for thresholds & phases).
 - Flag: `allow_legacy_cook_create` introduced (default False) gating former legacy cook task create fallback.
 - Pocket 7: Rate limiting infrastructure (Protocol + memory/redis backends, fixed-window helper, @limit decorator).
 - Metrics: `rate_limit.hit` (tags: name, outcome, window) instrumentation in decorator.
 - Feature flag `rate_limit_export` (opt-in per tenant) gating export CSV rate limits (5/minute per tenant:user).
 - 429 error envelope now includes `retry_after` and `limit` fields when raised by rate limiter.
 - Audit persistence (AuditEvent model + migration) and listing endpoint `GET /admin/audit` (paged, filters: tenant_id, event, from/to inclusive, q text search) with `X-Request-Id` response header.
 - Structured request logging including `request_id` correlated with audit events.
 - OpenAPI: Added `AuditView`, `PageResponse_AuditView` schemas and refined query parameter docs & header component for `X-Request-Id`.
 - CLI: `scripts/audit_retention_cleanup.py` for retention purge (`--days`, `--dry-run`).
 - Token Bucket limiter (memory + Redis) with per-limit `strategy` and optional `burst` in registry.
 - Redis token bucket tests (skip automatically if Redis unavailable).
- Import API: enhetliga svarstyper `ImportOkResponse | ImportErrorResponse` i OpenAPI.
- Import API: `meta.format` ( "csv" | "docx" | "xlsx" ) och förtydligad `415 Unsupported Media Type`-beskrivning ("unsupported or mismatched content-type/extension").
- Docs: markdownlint konfiguration + GitHub Action; Ruff exkluderar nu *.md.

### Changed
- SQLAlchemy 2.x: ersatt `Query.get()` med `Session.get()` i core-moduler.
- RBAC/ägarskap: konsekvent `403` vid roll/tenant-missmatch (404 enbart för verklig frånvaro).
- 403 error body now enriched with `required_role`; legacy inline error handlers removed in favor of centralized `core.app_errors`.
- Tasks create: Added legacy `cook` fallback (canonical viewer blocked; raw role `cook` still allowed create). Decorator widened + in-function guard emitting `required_role: editor` for pure canonical viewers.
 - Documented Retry-After precision (ceil seconds, min 1) unified across fixed and token bucket strategies.
- Import CSV: tom fil/header-only är bakåtkompatibelt `200` med `ok: true`, `rows: []`, `meta.count: 0` (tidigare strikt plan föreslog 400).

### Tests
- Tasks: 13 + extra edge-tester (create/list, not_found, isolation, role, bad type, legacy done mapping).

### Notes
- TaskStatus utökad: `"todo" | "doing" | "blocked" | "done" | "cancelled"`.
# Unreleased

### Added
- Unified Portal – Meal Details (Planera Day) Phase 1–2
	- Adds `templates/ui/unified_planera_day.html` for `/ui/planera/day?ui=unified`.
	- Shows menu, special diets (specialkost) with counts, registrations, and Alt 2 for a single site/department/date/meal.
	- Adds read-only placeholders for future modules: Prepp, Inköp, Frys, Recept.
	- Covered by `tests/ui/test_unified_planera_day_phase1.py` and `tests/ui/test_unified_planera_day_phase2.py`.
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

## [0.3.1] - 2025-10-01 (Typing Wave 2 & Tooling Baseline)
### Internal / Code Quality
- Achieved mypy clean state (0 errors) across core runtime and active module services.
- Introduced TypedDict for JWT decode payload (`DecodedToken`) eliminating `Any` return.
- Refactored DB engine init to remove unreachable branches; clarified force re-init semantics.
- Normalized service return types (menu, diet, attendance, portion, turnus) with explicit annotations & assertions.
- Removed legacy `# type: ignore` comments where no longer needed; added minimal helper for dynamic `menu_service` attribute resolution.
- Refactored portion recommendation selection loops to reduce false positive unreachable warnings.

### Lint / Static Analysis
- Ruff baseline locked to `E,F,I` (errors, pyflakes, import sorting) – all passing.
- Planned next rule expansion: `B`, `UP`, `Q` (pending).
- Added Developer Tooling README section (usage of `ruff check` & staged mypy adoption strategy).

### Developer Notes
- Established v0.3.1 tag as stable starting point before broadening lint rule set.
- Next steps: expand Ruff rules, add badges, document example type error remediation, phase out ignore blocks in `mypy.ini`.

## [Unreleased]
### Added
- Admin write endpoints (/admin/limits POST/DELETE): optional flag-gated rate limit (`rate_limit_admin_limits_write`) default OFF; registry default `admin_limits_write` = 10 per 60s.
### Internal / Code Quality
- Introduced first strict mypy pocket (`core.jwt_utils`, `core.rate_limit`, `core.audit`, `core.db`) with `strict = True` enforcement.
- Added PIE & SIM Ruff rule groups; resolved all simplification warnings in core.
- Added pre-commit hooks (Ruff lint+format, mypy, merge marker guard).
- README updated with strict pocket workflow and active modules list.
 - Added second strict mypy pocket: `core.portion_recommendation_service`, `core.menu_service`, `core.service_metrics_service` (TypedDict structures for menu week view & service metrics rows; refined recommendation output typing).
 - Added third strict mypy pocket: `core.auth`, `core.feature_flags`.
	 - JWT payloads now explicit `AccessTokenPayload` & `RefreshTokenPayload` TypedDicts with claim validation (issuer defaulting, temporal skew handling, strict `type` enum, `nbf` guard).
	 - Feature flags refactored to typed registry (`FlagDefinition`, `FlagState`, `FlagMode`) with idempotent `add()` supporting string shorthand; `has()` helper for app factory integration.
	 - Expanded unit tests: JWT edge cases (missing claim, unknown type, bad signature, expired, nbf future, skew boundary) & feature flag registry behaviors (idempotent add, unknown flag error, disable/enable cycle, sorted listing).
	 - Definition of Done checklist for typing/security PRs documented in README.
 - Added fourth strict mypy pocket: `core.api_types`, `core.admin_api`, `core.diet_api`, `core.service_metrics_api`, `core.service_recommendation_api`.
	 - Centralized API contracts in `core/api_types.py` (TypedDict + NewType IDs, unified ok/error envelope).
	 - Annotated API handlers with precise union return types (Ok vs ErrorResponse) while preserving runtime JSON.
	 - Added 8 contract smoke tests (happy + error per module) ensuring structural stability.

### Importers (Pocket 8)
- Added `core/importers` package with strict typing pocket (CSV & DOCX table ingest).
- New modules: `base_types` (RawRow dict, NormalizedRow TypedDict, structured ErrorDetail & exceptions), `csv_importer`, `docx_table_importer`, `validate` (schema & value validation).
- Validation: missing column, empty required value, invalid int, unexpected extra column (all aggregated into `ImportValidationError`).
- Tests: CSV (happy, blank lines, missing column, empty value, invalid int, unicode, extra column) and DOCX (happy, empty table, missing required, library-missing fallback) with skip if `python-docx` absent.
- mypy: Enabled `strict = True` for `core.importers.*` (excluding legacy `docx_importer` kept under ignore for now) and removed dynamic TypedDict workaround by using `dict[str,str]`.
- Lint: Importer modules pass expanded Ruff rules (imports, UP, B, SIM, PIE) with modern typing (PEP 604 unions).
- Pagination: Introduced unified `PageResponse` envelope for `/tasks/` and `/notes/` list endpoints with `meta {page,size,total,pages}` and query params `page,size,sort,order` (size capped at 100; defaults page=1,size=20).
### Import API Enhancements
- Added `/import/menu` endpoint (dry-run diff) documented in OpenAPI with `dry_run` query parameter and `meta.dry_run` boolean.
- Extended `ImportOkResponse.meta` schema to include optional `dry_run` property.
- Added OpenAPI test coverage for new path & schema.
- Hardened `core.import_api` under strict mypy: unified error envelope helper `_error()`, removed ad-hoc `jsonify` duplicates, eliminated invalid `# type: ignore` usages, added precise typings for normalization pipeline and rate limit gate.

### Deprecations
- Centralized deprecation header emission via `core.deprecation.apply_deprecation`.
- Added RFC 8594 headers for legacy alias keys `notes` and `tasks` (pagination responses now primary via `items`).
	- Headers: `Deprecation: true`, `Sunset: Wed, 01 Jan 2026 00:00:00 GMT`, `Link: <https://example.com/docs/deprecations#notes-tasks-alias>; rel="deprecation"`, and `X-Deprecated-Alias: <comma-list>`.
	- Telemetry metric: `deprecation.alias.emitted{endpoint,aliases}` for monitoring removal readiness.
	- Consumers should migrate to `items` before the sunset date; alias removal tracked in DECISIONS.

### Rate Limiting
- Added per-tenant rate-limit registry (`core.limit_registry`) with resolution order tenant override → global default → fallback (5/60).
 - Audit persistence (AuditEvent model + migration) and listing endpoint `GET /admin/audit` (paged, filters: tenant_id, event, from/to inclusive, q text search) with `X-Request-Id` response header.
 - Structured request logging including `request_id` correlated with audit events.
 - OpenAPI: Added `AuditView`, `PageResponse_AuditView` schemas and refined query parameter docs & header component for `X-Request-Id`.
- Environment configuration: `FEATURE_LIMITS_JSON` (tenant:<id>:<name>) and `FEATURE_LIMITS_DEFAULTS_JSON` (global defaults).
- Decorator `@limit` now supports implicit lookup when `quota`/`per_seconds` omitted (`use_registry=True`).
- Metric `rate_limit.lookup{name,source}` emitted for each lookup (source ∈ tenant|default|fallback).
- Export endpoints now fetch quotas from registry (still gated by `rate_limit_export` flag).
- Added admin inspection endpoint `/admin/limits` returning paginated effective limits (defaults only or union with tenant overrides). Supports `tenant_id`, `name` filters and exposes `source` (tenant|default|fallback); fallback only shown for explicit name filter misses.
- Added write endpoints: `POST /admin/limits` (upsert tenant override) and `DELETE /admin/limits` (idempotent removal). Clamps quota/per_seconds, returns mutation envelope with `updated` or `removed` flags.
- Added audit logging for admin limits mutations (`limits_upsert`, `limits_delete`) capturing tenant_id, name, quota/per_seconds (upsert), updated/removed flag, actor_user_id, actor_role.

## [1.0.0] — 2025-10-10
### Added
- README: “Strict typing pockets (RC1)” section.
- GA checklist template (`docs/GA_CHECKLIST_ISSUE.md`).

### Changed
- Standardized RFC7807 documentation and verification guidance.

### Fixed
- Ruff auto-fixes applied ahead of RC tag.

## [1.8.0] — 2025-11-10 (Admin Phase B)
### Added
- Admin: write persistence for Sites, Departments, Diet Defaults, Alt2 bulk (idempotent upsert) with optimistic concurrency (ETag/If-Match).
- Alembic migration `0008_admin_phase_b.py` introducing tables (sites, departments, diet_types, department_diet_defaults, alt2_flags) and version/updated_at columns & triggers (Postgres/SQLite).
- OpenAPI: collection ETag for Alt2 W/"admin:alt2:week:{week}:v{n}" and per-item ETags; headers documented across endpoints; 412 ProblemDetails includes `current_etag`.

### Changed
- OpenAPI info.version bumped to 1.8.0; Department schema updated to `resident_count_mode` (enum: fixed|per_day_meal) and `resident_count_fixed`.
- Alt2: constraints and indexes for performance (CHECK week 1..53, weekday 1..7, FKs ON DELETE CASCADE; indexes on (department_id,week) and (week,department_id,weekday)).

### Backward compatibility
- Read endpoints and previously released clients remain unaffected; new write paths are additive and gated behind `ff.admin.enabled`.

