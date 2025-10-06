## Architectural / Typing Decisions

### 2025-10-01 Pocket 5: Tasks Strict Typing
Context: Introduced strict mypy pocket for `core.tasks_api` and new `core.tasks_service`.

Decisions:
1. Added explicit task contracts in `core/api_types.py` (TaskStatus Literal with full lifecycle statuses, Task* TypedDicts).
2. Service layer (`tasks_service`) requires explicit RBAC context parameters: `tenant_id`, `user_id`, `role` to eliminate hidden session coupling.
3. API returns standardized success envelopes with `ok: True` and error envelopes with `ok: False` (extended generic error handling in `app_factory._json_error`).
4. Update endpoint exposed via both PUT and PATCH for forward compatibility with partial updates; implementation remains idempotent.
5. Kept legacy full task serialization for create/update responses (optional `task` field) while minimal summaries used in list for performance.

Rationale:
- Incremental strict typing pocket strategy reduces review surface and risk.
- Explicit context parameters improve testability and future extraction of service layer.
- Consistent envelopes simplify frontend handling and automated tests.

Follow-ups:
- Replace legacy `Query.get()` with `Session.get()` (SQLAlchemy 2.x idiom) in tasks module.
- Expand TaskSummary with assignee/due when those fields become stable.
- Consider consolidating PUT/PATCH once clients adopt PATCH.

### 2025-10-01 Error Envelope Consistency
Changed global error handlers to include `ok: False` to align with newer pockets (admin, tasks) unified envelope model.

Impact: Existing clients expecting only `{error, message}` continue to work (added field is additive) while new clients/tests rely on the boolean guard.
# Architectural & Typing Decisions

This log captures incremental design choices for traceability.

## 2025-10-01 Token Payload Separation
We introduced explicit `AccessTokenPayload` and `RefreshTokenPayload` `TypedDict`s instead of a single union-with-optional-fields model. Rationale:
- Prevent silent `Any` leakage on decode by returning a precise variant.
- Avoid inheritance field overwrite issues (`type` narrowing) encountered with a base dict.
- Enable future additions (e.g., `scope`, `session_version`) to one token type without loosening the other.

Validation rules now enforced in `decode()`:
- Required claims: `sub`, `role`, `tenant_id`, `jti`, `iat`, `exp`, `type`.
- `iss` (issuer) defaults to literal `"yuplan"` if absent (backward compatibility) but is included in new issued tokens.
- Temporal checks: `exp` must be > now - skew; optional `nbf` must be <= now + skew.
- Reject unknown `type` values early.

## 2025-10-01 Feature Flag Registry Typing
Replaced ad-hoc / implicit structures with:
- `FlagDefinition` (`name`, `mode`) and `FlagState` (`name`, `enabled`, `mode`).
- `FlagMode` literal currently limited to `"simple"` (future: percentage, gradual, per-tenant targeting).
- `FeatureRegistry.add()` accepts either a full definition or simple string shorthand; idempotent to avoid accidental mode mutation.
- Added `has()` for cleaner integration where existence check precedes add.

## 2025-10-01 Strict Pocket 3 Introduction
Modules `core.auth` and `core.feature_flags` moved under `strict = True` in `mypy.ini` completing Pocket 3. Criteria:
- Zero mypy errors under strict.
- Comprehensive negative-path tests (JWT claim validation, signature tamper, temporal edges; flag add/list/enable cycles).

## Future Considerations
- Introduce Redis-backed rate limiter (typed wrapper) for multi-process deployments.
- Add `percentage` rollout mode with validated int 0-100 field; extend `FlagDefinition` accordingly.
- Consider extracting JWT logic into a dedicated security module if additional strategies (e.g., mTLS session binding) are added.
 - Centralize additional domain API contracts as pockets expand.

## 2025-10-01 Pocket 7: Rate Limiting Introduction
Context:
Implemented first iteration of a typed, pluggable rate limiting layer to support gradual opt-in of protective quotas without global risk.

Decisions:
1. Algorithm: Fixed-window (second-aligned) for simplicity; consider sliding or token-bucket later for burst smoothing.
2. Abstraction: `RateLimiter` `Protocol` with `allow(key, quota, per_seconds)` + `retry_after(key, per_seconds)` enabling backend polymorphism (memory, Redis, noop).
3. Backends:
	- `memory`: deterministic single-process testing backend.
	- `redis`: production path using `INCR` + `EXPIRE` (on first increment); TTL sources `retry_after`.
	- `noop`: default disabled behavior (safeguards rollout).
4. Decorator: `@limit(name, quota, per_seconds, key_func, feature_flag?, flag_opt_in=True)` resolves limiter lazily per request (testability) and supports feature-flag gating bypass.
5. Metrics: Emits `rate_limit.hit` with tags: `name`, `outcome` (allow|block), `window`.<br>Use metrics to size real quotas before enabling broadly.
6. Error Contract: 429 now includes JSON `{ok:false,error:'rate_limited',message,retry_after,limit}` and `Retry-After` header.

Rationale:
Small typed surface limits risk while providing observability & future extensibility.

Follow-ups:
* Evaluate need for sliding/window smoothing.
* Add per-tenant configurable quotas (DB persisted) when at least one production endpoint is stable under limits.
* Metric cardinality guard: optionally sample or aggregate for high-cardinality keys.

## 2025-10-01 Export Rate Limit Flag (`rate_limit_export`)
Decision: Protect CSV export endpoints via opt-in tenant flag rather than global default ON.

Mechanics:
* Flag OFF → decorator bypass (zero rate-check cost beyond dictionary lookup).
* Flag ON → quota 5 / 60s per `tenant_id:user_id` composite key (`export_notes_csv` and `export_tasks_csv` tracked separately).

Rationale:
Exports can be bursty (backfills); premature throttling risks breaking legitimate workflows. Opt-in yields safer staged rollout and metrics baseline.

Future:
* Consider raising quota or switching default to ON after observing low block rate.
* Possibly differentiate heavy/bulk exports vs. quick user exports with separate keys/quotas.

## 2025-10-01 API Contract Centralization (Pocket 4)
All public HTTP handler response shapes consolidated into `core/api_types.py`:
- Use `TypedDict` + `NewType` for ID fields (`TenantId`, `UnitId`, `DietTypeId`, `AssignmentId`) to prevent accidental cross-assignment.
- Unified envelope: success objects have `ok: True`; errors represented as `{ok: False, error: code, message?: str}`.
- Optional, non-nullable fields use `NotRequired[...]` instead of `| None` to distinguish absence vs explicit null.
- Handlers return precise unions (e.g., `TenantListResponse | ErrorResponse`) with minimal `cast()` where constructing dynamic dicts.

Rationale:
- Single source of truth for client contracts.
- Eases future strict pockets (handlers remain thin, contracts stable).
- Reduces ad-hoc dict construction mistakes (missing keys, inconsistent casing).

## 2025-10-01 Literal ok Modeling
`ok` modeled as `Literal[True]` in success types and `Literal[False]` in `ErrorResponse` to allow mypy to discriminate unions reliably without runtime tag fields.

## 2025-10-01 NewType Identifier Strategy
Adopted `NewType` for tenant/unit/diet/assignment IDs to:
- Catch accidental mix-ups (passing a unit id where a diet type id expected) during static analysis.
- Keep runtime cost nil (NewType erases at runtime) while maintaining clarity.

Migration Plan:
- Consider applying NewType to additional identifiers (e.g., UserId, MenuId) in future pockets once service layers are strict.

## 2025-10-01 Session persistence on login
`auth.login()` now stores `user_id`, `role`, `tenant_id` in the Flask session in addition to issuing JWTs.
- Motivation: Several flows and legacy tests assumed a server-side session, causing sporadic 401s after recent refactors relying on bearer tokens only.
- Future: Once all tests use bearer-only flows we can optionally gate this behind a config flag.

## 2025-10-01 FeatureRegistry back-compat
Introduced alias `_flags` referencing the internal enabled set to satisfy older tests/clients poking into a previous internal structure.
- Primary canonical state remains `_enabled` + `_defs`.
- `_flags` may be removed in a major version once external usages are migrated.

## 2025-10-01 UP038 policy (runtime vs. type hints)
Adopted policy: Apply Ruff UP038 (PEP 604 `|` unions) only to annotations. Retain runtime `isinstance(x, (int, float))` tuple patterns for clarity/performance.
Where Ruff flags these runtime checks, add targeted `# noqa: UP038` comments with rationale.

### 2025-10-01 Pocket 6: Modularization (Errors / Sessions / AuthZ)
Context: Extracted cross-cutting concerns (error envelope, session shaping, role-based authorization) into dedicated strict modules to reduce duplication and prepare for further domain pocket extractions.

New Modules (all under `strict = True`):
1. `core.app_errors` – Central JSON error envelope creation (`make_error`) and Flask error handler registration (`register_error_handlers`). Provides consistent `{ok: False, error, message?}` across 400/401/403/404/409/422/429/500.
2. `core.app_sessions` – Minimal `SessionData` (`user_id`, `role`, `tenant_id`) retrieval & persistence. Utility `persist_login`, `get_session`, `require_session` (typed access point). Role Literal baseline: `superuser|admin|editor|viewer`.
3. `core.app_authz` – Role decorator `require_roles`, tenant enforcement (`enforce_tenant`), and helper `can_modify` centralizing mutability policy.

Error Policy Clarification:
- 403 for RBAC mismatch or tenant ownership violation.
- 404 strictly for absent resources (not authorization failures).
- Internal errors mapped to `internal` while preserving generic message.

Rationale:
- Isolate generic concerns: prevents subtle drift in envelope shape across handlers.
- Eases future pocket migrations (handlers import a stable surface instead of re-implementing guards).
- Strengthens mypy discrimination (single source for `ErrorCode`).

Deferred / Follow-ups:
- Replace legacy inline `require_roles` usages by migrating endpoints gradually to `core.app_authz`.
- Introduce richer `Role` taxonomy per domain if needed (tasks vs. flags) with composition rather than widening Literal prematurely.
- Potentially expose a structured exception type to replace `RuntimeError` placeholders for internal control flow.

DoD Achieved (Pocket 6 baseline):
- Skeleton modules created; strict typing enabled (0 new ignores expected).
- Smoke tests (401/403/404 + session persistence) planned to assert contract stability.

### 2025-10-01 Role Adapter Introduction
Introduced `core.roles` with canonical roles (`superuser|admin|editor|viewer`) and legacy mapping (`cook->viewer`, `unit_portal->editor`). `to_canonical()` applied within `require_roles` to harmonize authorization checks without changing stored session values.

### 2025-10-01 require_roles Canonical Enforcement
`require_roles` now accepts `RoleLike` (canonical or legacy) and emits `required_role` (canonical) in 403 responses. Central error handlers augmented to surface AuthzError / SessionError uniformly.

### 2025-10-01 OpenAPI Restoration & Validation
Context: Earlier refactors temporarily collapsed the OpenAPI spec to a minimal placeholder risking undocumented drift.

Decisions:
1. Reconstructed full OpenAPI 3.0.3 document directly in `app_factory.openapi_spec()` including Features (list/toggle), Admin Feature Flags, Notes (CRUD), Tasks (CRUD + status semantics) with shared Error schema & enriched 403 examples containing `required_role`.
2. Added dedicated structural validation test `tests/test_openapi_full.py` asserting presence of critical paths, schemas, and the enriched forbidden example to guard against accidental contraction.
3. Treat spec as source of truth; future endpoint additions must add both implementation + spec + minimal validation assertion in the OpenAPI test.

Rationale:
- Prevent silent API surface regressions during ongoing modularization & exception-flow transition.
- Accelerate client generation & contract review (spec completeness maintained in-tree).
- Ensures enriched authorization error shape (`required_role`) remains documented.

Follow-ups:
- After exception-flow migration (raising AuthzError/SessionError), add securitySchemes & standardized error response refs where missing.
- Consider extracting spec assembly into a composable builder if growth increases duplication pressure.

### 2025-10-01 Tasks Create Legacy Cook Fallback
Context:
Migrating Tasks create endpoint to canonical role model (`viewer|editor|admin`) tightened creation to `editor+`. Legacy tests expected historical behavior where `cook` (now mapped to canonical `viewer`) could still create tasks.

Decision:
1. Broadened POST /tasks decorator to include `viewer` so legacy `cook` survives initial guard.
2. Added in-function conditional: if canonical role is `viewer` and raw session role != `cook`, raise `AuthzError(required="editor")`.
3. This preserves backward compatibility for `cook` without granting blanket create to new canonical `viewer` roles.

Rationale:
- Avoids introducing a bespoke pseudo-role while honoring legacy contract.
- Keeps surface explicit: error still communicates `required_role: editor` to purely canonical viewers.
- Localized workaround; no changes required to Shared `require_roles` logic or `to_canonical` mapping table.

Alternatives Rejected:
- Adding `cook` to canonical role set (would leak legacy vocabulary forward).
- Maintaining original stricter editor/admin policy and rewriting legacy tests (risk of downstream client breakage).

Follow-ups:
- Revisit once all legacy clients migrated; remove fallback branch and tighten decorator to `editor|admin` only.
- Add metric hook (future) to measure cook-based creation usage pre-removal.
	- (Implemented) Metric `tasks.create.legacy_cook` increments with tags: tenant_id, user_id, role, canonical.

	### 2025-10-01 Legacy Cook Create Deprecation Plan & Thresholds
	Goal: Retire legacy cook create fallback without breaking existing tenants.

	Metric of record: `tasks.create.legacy_cook` (tags: tenant_id, user_id, role, canonical).

	Deprecation thresholds:
	- Global low usage: rolling 14 days < 5 total events.
	- Per-tenant low usage: < 1 event/week for 3 consecutive full weeks.

	Phases (N = decision date / start of Observation):
	1. Observe (N → N+14d): measurement only, no behavior change.
	2. Warn (N+14d → N+28d): once thresholds are met, emit rate-limited (max 1/tenant/day) warn log on fallback path (tags include deprecated="soon").
	3. Default Change (≥ N+28d): set `allow_legacy_cook_create = False` for new tenants only (existing retain current behavior).

### 2025-10-01 Pocket 8: Importers (CSV & DOCX Table)
Context:
Needed a typed ingestion pipeline for simple tabular imports (initial scope: tasks-like rows) with deterministic validation & early mypy strict adoption.

Decisions:
1. Raw Representation: Use `dict[str, str]` (`RawRow`) instead of a permissive `TypedDict` for dynamic headers to avoid spurious `literal-required` mypy errors and simplify mapping logic.
2. Validation Layer: Central `validate_and_normalize()` returning `list[NormalizedRow]` or raising `ImportValidationError` with structured `ErrorDetail` entries (codes: `missing_column`, `empty_value`, `invalid_int`, `unexpected_extra_column`). All errors are currently fatal (fail-fast for user feedback clarity) but structured list allows future partial acceptance.
3. Normalized Schema: Minimal stable `NormalizedRow` (`title`, `description`, `priority:int`) chosen to keep downstream persistence decoupled from raw import volatility.
4. Format Handling: Separate lightweight parsers: `csv_importer.parse_csv(text)` and `docx_table_importer.parse_docx(bytes)` each responsible only for structural extraction + whitespace/BOM stripping; no semantic validation (single responsibility).
5. Optional Dependency: `python-docx` guarded import; raising `UnsupportedFormatError` when missing so environments can exclude heavy dependency without breaking CSV path.
6. Strict Typing: Enabled `strict = True` pocket for `core.importers.*` (excluding legacy `docx_importer` menu parser left under ignore to limit blast radius).
7. Lint Policy: Adopted modern typing (`list[...]`, PEP 604 unions) and resolved Ruff rules (imports ordering, UP, B, SIM, PIE) during initial introduction to avoid later churn.

Rationale:
- Early strict typing ensures import edge cases (missing/extra columns) surface during development rather than runtime.
- Structured `ErrorDetail` enables UI surfacing of per-row, per-column issues without parsing free-form strings.
- Isolation of parsing vs. validation keeps future format additions (e.g., XLSX, JSON Lines) straightforward.

Alternatives Considered:
- Using Pandas for parsing rejected (heavy dependency, slower cold start, overkill for narrow schema).
- Accepting extra columns silently rejected; explicit error fosters user correction and prevents unnoticed data loss.

Follow-ups:
- Add streaming / chunked parsing for very large files when needed (current approach loads all rows in memory).
- Introduce partial acceptance mode (ingest valid rows, report invalid) behind a feature flag.
- Extend `NormalizedRow` with optional fields (e.g., tags) using `NotRequired[...]` to maintain backwards compatibility.

### 2025-10-01 OpenAPI Extension: `/import/menu` Dry-Run
Context: Needed a documented path for weekly menu ingestion (currently dry-run diff only) to stabilize future UI consumption.

Decisions:
1. Added `/import/menu` POST with `dry_run` query parameter (boolean; `?dry_run=1` triggers diff-only behavior).
2. Reused `ImportOkResponse` schema; extended `meta` to optionally include `dry_run: true`.
3. Response includes both normalized `rows` (generic mapping of menu variants) and raw `diff` (legacy variant fields + action placeholder).
4. Optional importer object `_importer` remains pluggable for tests; 415 returned when unavailable.

Rationale:
- Keeps initial contract minimal while leaving room to add persistence semantics later.
- Reuse of existing schema avoids schema proliferation and redundant tests.

Follow-ups:
- Add persistence path (non-dry-run) with idempotent upsert semantics.
- Include variant action differentiation (create/update/skip) once existing menu read model stabilized.
- Document authentication/authorization specifics once cook/editor separation clarified for menu operations.

### 2025-10-01 Deprecation: Pagination Alias Keys `notes` / `tasks`
Context: Unified pagination envelope (`items`, `meta`) introduced; legacy tests & some clients still read `notes` / `tasks` top-level arrays.

Decisions:
1. Continue emitting alias keys for backward compatibility but mark responses with RFC 8594 deprecation headers when aliases are present:
	- `Deprecation: true`
	- `Sunset: Wed, 01 Jan 2026 00:00:00 GMT`
	- `Link: <https://example.com/docs/deprecations#notes-tasks-alias>; rel="deprecation"`
2. Headers configurable via env (`DEPRECATION_NOTES_TASKS_SUNSET`, `DEPRECATION_NOTES_TASKS_URL`).
3. Tests assert presence of headers to prevent accidental removal or silent date change.

Rationale:
- Provides explicit migration signal without breaking current consumers.
- Sets a clear removal timeline aiding roadmap transparency.

Removal Plan:
1. Monitor client adoption; announce 1–2 minor releases ahead if extension needed.
2. At / after sunset date: remove alias injection + header emission; update CHANGELOG and README.
3. Provide final notice in release notes one version before removal.

Follow-ups:
- Consider adding structured `X-Deprecated-Alias` header listing the exact alias keys present for multi-alias contexts in future endpoints.

### 2025-10-02 Centralized Deprecation Helper
Context: Multiple endpoints needed identical RFC 8594 deprecation headers for legacy alias keys; logic was duplicated.

Decision:
1. Introduced `core.deprecation.apply_deprecation(resp, aliases, endpoint, sunset?, url?)` to uniformly set `Deprecation`, `Sunset`, `Link`, and `X-Deprecated-Alias` headers.
2. Emits metric `deprecation.alias.emitted` with tags `{endpoint, aliases}` for observability and removal readiness tracking.
3. Notes and Tasks list endpoints refactored to call the helper after alias injection.

Rationale:
- Removes header construction duplication.
- Centralizes default sunset & documentation URL derived from environment overrides.
- Provides a single upgrade point for future enhancements (e.g., version negotiation, per-alias metadata).

Follow-ups:
- Extend helper to optionally accept structured deprecation reasons and planned removal version.
- Add sampling guard if emission rate becomes high across many endpoints.

### 2025-10-02: Per-tenant rate-limit registry
- **Motiv:** Konfigurerbara kvoter per tenant/limit utan kodändring.
- **Resolution order:** tenant override → global default → safe fallback.
- **Clamp/caps:** `quota ≥ 1`, `1 ≤ per_seconds ≤ 86400`.
- **Precedens:** Explicit `quota/per_seconds` i dekorator **överstyr** registry.
- **Telemetri:** `rate_limit.lookup {name, source}` för driftinsikt.
- **Rollout:** Export-endpoints använder registry bakom `rate_limit_export` (flagga).
	4. Opt-out (N+28d → N+56d): auto-disable fallback for tenants with 0 events in prior 30d; first blocked attempt logs info with guidance.
	5. Removal (≥ N+56d): remove fallback branch + tests; update CHANGELOG, README, OpenAPI examples if needed.

	Communication:
	- CHANGELOG note each phase transition.
	- Internal list of tenants still generating events reviewed weekly.

	Operational queries (illustrative; adapt to log stack):
	```
	# Global 14d count
	grep -E "metric name=tasks.create.legacy_cook" app.log | awk '...count...'

	# Per-tenant (tenant_id=7)
	grep -E "metric name=tasks.create.legacy_cook" app.log | grep "'tenant_id': '7'" | wc -l
	```

	Warn phase implementation (future PR):
	- Env toggle `LEGACY_COOK_WARN=true` gates emission until automated threshold detection exists.
	- Log name: `metrics` or `authz`; message: `deprecated_legacy_cook_create used tenant=<id> user=<id>`.
	- Optional: augment metric tags with `deprecated="soon"`.

	Feature flag introduction (Phase 3):
	- Flag: `allow_legacy_cook_create` (default True now; becomes False for new tenants at Phase 3).
	- Tests to cover cook allowed/blocked and viewer always blocked.

	Removal checklist:
	- Delete fallback conditional from `create_task`.
	- Remove metric-specific decision entries if no longer relevant.
	- Drop tests: `test_metrics_legacy_cook*` & legacy cook create path assertions.
	- Update CHANGELOG & README (Metrics section) to reflect removal.
	- Add migration note if any stored configs (flags) cleaned up.

### 2025-10-01 Flag Gate Activation (`allow_legacy_cook_create`)
Decision: Do not wait for full 14d observation; enforce canonical policy immediately and make legacy cook allowance opt-in via per-tenant feature flag `allow_legacy_cook_create`.

Details:
- Default: False (legacy cook blocked like canonical viewer).
- When True for a tenant: legacy cook path re-enabled (metric + optional warn logic still active).
- Applies only to raw role `cook`; canonical viewer without raw cook remains forbidden.
- Metrics: Still emits `tasks.create.legacy_cook` (with `deprecated=soon` tag if warn phase enabled).

Rationale:
- Eliminates uncertainty window; prevents accidental reliance in production tenants.
- Aligns with principle of explicit opt-in for compatibility quirks.
- Simplifies eventual removal (tenants either migrated or explicitly flagged).

Testing Impact:
- Updated cook-allow tests now enable flag explicitly.
- Added negative test ensuring cook blocked without flag.

Follow-ups:
- Track flag usage; once zero active tenants for fixed window, proceed to removal phase directly.

## 2025-10-02: Import CSV – tom fil (compat 200)
Decision: Tom CSV / header-only svarar 200 OK med ok: true, rows: [], meta.count: 0.

Context: Äldre testflöde och klienter förväntar 200 även när inga rader finns. Striktare policy (400) hade brutit dessa.

Alternatives:
- 400 Bad Request – strikt validering (avvisat nu)
- Flag-styrt beteende – ev. senare

Consequences:
- Bakåtkompatibelt; klienter kan använda meta.count==0 för att särskilja.
- Möjlighet kvarstår att införa strikt variant bakom feature flag.

Notes:
- OpenAPI speglar kontraktet; meta.format dokumenterat.
- 415 för icke-stöd / mismatch MIME/extension oförändrat.

