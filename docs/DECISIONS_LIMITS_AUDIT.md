# Decision: Audit logging for admin limits mutations

Date: 2025-10-02
Status: Accepted

## Context
Admin endpoints now allow GET/POST/DELETE of rate limit definitions (tenant overrides). For traceability and security posture (future SOC2 readiness) we must record successful mutations.

## Decision
Emit audit events on successful write operations only:
- Event `limits_upsert` with fields: tenant_id, name, quota, per_seconds, updated, actor_user_id, actor_role.
- Event `limits_delete` with fields: tenant_id, name, removed, actor_user_id, actor_role.

Implementation:
- Implemented in `core.admin_api` after confirming 2xx success.
- Wrapped in try/except to avoid user-facing failures if audit backend misbehaves.
- Uses existing `core.audit.log_event` interface (fallback no-op if unavailable).

## Rationale
- Minimal field set: sufficient to reconstruct who changed what and when.
- Avoids storing PII beyond numeric actor_user_id.
- Separation from metrics: metrics are aggregated; audit retains per-event fidelity.

## Alternatives Considered
- Pre-flight audit (before mutation) – rejected (could log failed attempts incorrectly).
- Including full previous limit snapshot – rejected (not needed for first phase; can be added later as `prev_quota`, `prev_per_seconds`).

## Consequences
- Introduces low overhead call per mutation.
- Enables future alerting on unexpected burst of changes.

## Future Enhancements
- Add previous values to `limits_upsert` when updating.
- Add correlation_id / request_id linking to HTTP logs.
- Export audit stream to external SIEM.
