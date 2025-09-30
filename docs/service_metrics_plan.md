# Service Metrics Integration Plan

## Goals
Provide a unified, extensible mechanism to ingest, store, and expose meal production & waste KPIs across tenants (offshore & municipal) without coupling to legacy calculation code.

## Core Entities (Already in Schema)
- `service_metrics` (per date, unit, meal, dish, category, produced/served/leftover)
- `portion_guidelines` (baseline portions, protein density for projections)

## Data Flow
1. Source events (manual entry, import, automated IoT, legacy adapter) -> normalized payload.
2. Validation & normalization (tenant + unit + meal + date + dish/category cross-check).
3. Persistence (upsert policy: unique by tenant_id + unit_id + date + meal + dish_id NULL-handling).
4. Aggregation endpoints (daily, weekly, per category, per dish) computed on demand initially.
5. Future optimization: materialized summary tables (`service_metric_summary_day`, `service_metric_summary_week`).

## API Surface (Phase 1)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/metrics/ingest` | POST | Batch ingest list of metric rows (validate + upsert) |
| `/metrics/query` | POST | Flexible filter (date range, unit(s), category, dish) returns raw rows |
| `/metrics/summary/day` | GET | Aggregate totals per day/unit/meal |
| `/metrics/summary/week` | GET | Weekly grouped summary (ISO week) |

All endpoints require roles: `superuser` or `admin` (read/write) and `unit_portal` (read-only: query + summaries).

## Validation Rules
- `date` ISO `YYYY-MM-DD`.
- `meal` in {`lunch`,`dinner`,`evening`} (extendable).
- Dish OR category required (category fallback when dish unknown).
- Numeric fields: non-negative; leftover <= produced; served <= produced.
- `served_g_per_guest` auto-calculated if not provided and guest_count + served_qty_kg present.

## Upsert Key
`(tenant_id, unit_id, date, meal, COALESCE(dish_id, -1), COALESCE(category,''))` — we treat missing dish as -1 sentinel with category distinguishing row.

## Computation Formulas
```
served_g_per_guest = (served_qty_kg * 1000) / guest_count  (if guest_count > 0)
leftover_pct = leftover_qty_kg / produced_qty_kg           (if produced > 0)
served_pct = served_qty_kg / produced_qty_kg               (if produced > 0)
```

## Phase Roadmap
- Phase 1: CRUD ingest + query + basic daily/weekly summaries (on-demand computation).
- Phase 2: Derived KPIs (leftover %, protein grams per guest using recipe or guideline protein density).
- Phase 3: Materialized summary tables + caching layer.
- Phase 4: Alerts / anomaly detection (high leftovers, low utilization).

## Testing Strategy
- Unit: validation (invalid meal, negative numbers, leftover > produced) rejects.
- Integration: ingest + re-ingest same key updates (idempotent upsert) -> counts stable.
- Summary: compare manual aggregation vs endpoint result.

## Open Questions
- Should portion guidelines auto-infer produced target? (Future: yes, variant: guideline * guest_count).
- Multi-meal mapping (breakfast/snacks) timeline? (Defer until explicit requirement).

## Security & Access
- Writes: admin/superuser only.
- Reads: unit_portal limited to its unit unless role elevated (enforce in query filter).

## Next Steps
1. Implement `ServiceMetricsService` with ingest/query/summary.
2. Add `/metrics` blueprint with endpoints above.
3. Add basic tests (ingest + summary math).