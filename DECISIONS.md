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
