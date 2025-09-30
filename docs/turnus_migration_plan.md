# Turnus (Rotation) Migration Plan

## Legacy Context
Legacy systems implement multi-pattern staff scheduling (e.g., offshore rotations) with domain concepts: rotation templates, shift blocks, roles, and ad-hoc overrides. Unified platform already has minimal scheduling tables:
- `shift_templates` (name, pattern_type)
- `shift_slots` (start_ts, end_ts, role, status, notes, optional template_id)

## Goals
1. Preserve existing functional coverage for offshore rotation planning.
2. Normalize patterns into parameterized `shift_templates` + generated `shift_slots`.
3. Support future municipal lightweight shifts using same primitives.

## Mapping Legacy -> Unified
| Legacy Concept | Unified Target | Notes |
|----------------|----------------|-------|
| Rotation pattern (e.g., 2/4, 14/21) | `shift_templates.pattern_type` + pattern detail JSON (Phase 2) | Phase 1 store canonical name only |
| Generated calendar shifts | `shift_slots` rows | Pre-generated for planning horizon |
| Role tags (Cook, Helper) | `shift_slots.role` | Maintain simple string role first |
| Status (planned, published, swap) | `shift_slots.status` | Extend enumerations later |
| Notes/remarks | `shift_slots.notes` | Direct copy |
| Unit / Rig scope | `shift_slots.unit_id` | Supports cross-tenant multi-unit |

## Phased Approach
### Phase 1 – Direct Import
- Create a rotation import utility that reads legacy rotation export.
- Translate each legacy shift block to a `shift_slot` with: start_ts, end_ts, role, status='planned'.
- Attach shifts to a template row (create one template per imported rotation pattern if missing).

### Phase 2 – Pattern Formalization
- Introduce JSON column or companion table `shift_template_rules` describing cycle length (days on/off) & anchor date.
- Add generation endpoint: `/turnus/generate?template_id=...&from=YYYY-MM-DD&to=...` producing new slots idempotently (skip duplicates).

### Phase 3 – Adjustments & Swaps
- Add swap requests table (not yet modeled) to track proposed exchanges.
- Extend `status` field: planned | published | swap_pending | swapped | canceled.

### Phase 4 – Analytics
- Derive utilization metrics, coverage gaps, overtime detection.

## Data Integrity Rules
- (tenant_id, unit_id, start_ts, end_ts, role) uniqueness optional guard (soft via query before insert).
- End time must be after start time.
- Generated cycle should not exceed planning horizon (configurable, e.g., 12 months).

## Proposed API (Initial)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/turnus/import` | POST | Batch import legacy shifts -> shift_slots |
| `/turnus/templates` | GET | List templates |
| `/turnus/templates` | POST | Create a template (name, pattern_type) |
| `/turnus/slots` | GET | Query slots (date range, unit, role) |
| `/turnus/generate` | POST | Generate slots from pattern rules (Phase 2) |

## Pseudo Data Model Additions (Phase 2)
```
shift_template_rules(
  id PK,
  template_id FK,
  cycle_length_days INT,
  on_days INT,
  off_days INT,
  anchor_start DATE
)
```
OR store a JSON structure in `shift_templates` (easier early):
```
pattern_json = {"cycle": 28, "on": 14, "off": 14, "anchor": "2025-01-01"}
```

## Migration Steps
1. Keep existing tables (already in initial migration).
2. Implement import endpoint writing raw slots.
3. Add pattern formalization in later migration (JSON column or new table).

## Testing Strategy
- Import: same number of shifts in payload vs stored rows (idempotent re-import updates? Optionally purge & reinsert).
- Generate: deterministic count for date span based on cycle math.
- Query: filter correctness (by unit, role, date range).

## Risks / Mitigations
- Time zone drift: store timestamps in UTC and ensure legacy import normalizes timezone.
- Duplicate shifts: implement hash check (tenant_id, unit_id, start_ts, end_ts, role) before insert.
- Pattern misalignment: verify anchor start aligns with generated cycle boundaries.

## Open Questions
- Need user-level assignment to shift slots? (Future: add `assigned_user_id`).
- Should swaps lock original slots or create shadow entries? (Leaning toward status mutation + separate swap record.)

## Next Implementation Tasks
1. Create `/turnus/import` + basic service (Phase 1).
2. Add template CRUD endpoints.
3. Add slots query endpoint.
4. Add basic tests (import & query).
