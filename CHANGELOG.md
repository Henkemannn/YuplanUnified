## Unreleased

### Added
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

### Changed
- SQLAlchemy 2.x: ersatt `Query.get()` med `Session.get()` i core-moduler.
- RBAC/ägarskap: konsekvent `403` vid roll/tenant-missmatch (404 enbart för verklig frånvaro).
- 403 error body now enriched with `required_role`; legacy inline error handlers removed in favor of centralized `core.app_errors`.
- Tasks create: Added legacy `cook` fallback (canonical viewer blocked; raw role `cook` still allowed create). Decorator widened + in-function guard emitting `required_role: editor` for pure canonical viewers.

### Tests
- Tasks: 13 + extra edge-tester (create/list, not_found, isolation, role, bad type, legacy done mapping).

### Notes
- TaskStatus utökad: `"todo" | "doing" | "blocked" | "done" | "cancelled"`.
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

### Deprecations
- Centralized deprecation header emission via `core.deprecation.apply_deprecation`.
- Added RFC 8594 headers for legacy alias keys `notes` and `tasks` (pagination responses now primary via `items`).
	- Headers: `Deprecation: true`, `Sunset: Wed, 01 Jan 2026 00:00:00 GMT`, `Link: <https://example.com/docs/deprecations#notes-tasks-alias>; rel="deprecation"`, and `X-Deprecated-Alias: <comma-list>`.
	- Telemetry metric: `deprecation.alias.emitted{endpoint,aliases}` for monitoring removal readiness.
	- Consumers should migrate to `items` before the sunset date; alias removal tracked in DECISIONS.

### Rate Limiting
- Added per-tenant rate-limit registry (`core.limit_registry`) with resolution order tenant override → global default → fallback (5/60).
- Environment configuration: `FEATURE_LIMITS_JSON` (tenant:<id>:<name>) and `FEATURE_LIMITS_DEFAULTS_JSON` (global defaults).
- Decorator `@limit` now supports implicit lookup when `quota`/`per_seconds` omitted (`use_registry=True`).
- Metric `rate_limit.lookup{name,source}` emitted for each lookup (source ∈ tenant|default|fallback).
- Export endpoints now fetch quotas from registry (still gated by `rate_limit_export` flag).

