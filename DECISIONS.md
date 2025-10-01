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
