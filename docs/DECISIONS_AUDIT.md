## 2025-10-02: Audit persistence & listing

Context: Originally audit events were ephemeral (in-memory log emission only). Need emerged for durable admin visibility, correlation with request logs, and future compliance retention.

### Event Minimum Fields
| Field | Reason |
|-------|--------|
| ts | Ordering, time window querying |
| tenant_id (nullable) | Multi-tenant scoping & filtering |
| actor_user_id (nullable) | Trace to user when session present |
| actor_role | Authorization / forensic context |
| event | Stable event key (e.g. `limits_upsert`) |
| payload (JSON) | Arbitrary structured details (limit name, changes) |
| request_id | Cross-link to structured HTTP log lines |

### Retention
- Configurable via env `AUDIT_RETENTION_DAYS` (default 90) — enforcement via a scheduled call to `AuditRepo.purge_older_than(days)` (cron / management command; not auto-run inside requests).
- Indexes: `(tenant_id, ts)` and `(event, ts)` chosen to cover dominant filter patterns (tenant scope drill-down & event-focused investigations) plus time-window queries.

### API Endpoint
`GET /admin/audit`
- Filters: `tenant_id`, `event`, `from` (inclusive), `to` (inclusive), `q` (case-insensitive substring search across serialized JSON payload), pagination (`page`, `size`).
- Ordering: `ts DESC` (newest first) — deterministic with auto-increment `id` as tie-breaker (implicit in insertion order).
- Response envelope: `PageResponse<AuditView>` + `X-Request-Id` header for correlation.

### Text Search Strategy
- Initial implementation uses `ILIKE` on `CAST(payload AS TEXT)` for substring search. Adequate for low-volume MVP; can evolve to GIN / FTS if Postgres adoption and scale require.

### Structured Logging Correlation
- Every response emits a structured JSON log line including `request_id` (either provided by client header `X-Request-Id` or server-generated UUID) plus tenant_id/user_id.
- Audit events persist the same `request_id` enabling end-to-end tracing.

### Failure Semantics
- Audit write failures are intentionally non-fatal to the primary business operation (best-effort). Failures may be logged (future improvement) but not surfaced to clients.

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| Synchronous external log aggregator (e.g. ELK) only | Harder to paginate / filter by tenant in-app; dependency coupling |
| Expanding all domain events (tasks, imports, etc.) immediately | Scope creep; start with admin limits & infra events first |
| Cursor-based pagination | Overkill for expected low initial volume; offset simpler |

### Future Enhancements
- Add metric `audit.insert.count` for ingestion observability.
- Optional actor impersonation tracking (original_user_id) if delegation is introduced.
- Retention enforcement job script with dry-run stats.
- Explicit event type registry (enum) to validate known keys.

### Summary
A lightweight, strictly typed repository + endpoint gives administrators auditable visibility while preserving future scalability paths (indexing, search upgrades). The design balances immediate observability needs with minimal operational overhead.

### Operational Tooling (2025-10-05 Update)
- Introduced CLI `scripts/audit_retention_cleanup.py` to perform retention purges outside request path.
- Flags: `--days` (defaults to `AUDIT_RETENTION_DAYS` or 90), `--dry-run` (no delete, only count).
- Exit codes: `0` success, `1` unexpected error, `2` invalid arguments (e.g. days < 1).
- Recommended schedule: nightly cron with dry-run monitored initially to establish expected churn before enabling deletes in production.
