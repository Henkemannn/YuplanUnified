# Migration Plan (Existing SQLite -> Unified Schema)

## Phase 0 – Backups
- Dump municipal kost.db -> municipal_backup.sqlite
- Dump offshore db -> offshore_backup.sqlite

## Phase 1 – Staging Extraction
- Create staging tables prefixed m_ and o_ mirroring originals.
- Copy raw rows.

## Phase 2 – Transform
- Dishes: union of offshore dishes + normalized municipal menu text tokens.
- Menus: municipal veckomeny -> menus + menu_variants (derive year = current if missing).
- Menu variants (Offshore) extracted from existing rotation mapping.
- Diet Types: municipal kosttyper -> dietary_types; link counts via avdelning_kosttyp.
- Attendance: municipal boende_antal rows; propagate default for days without overrides.
- Shift Slots: offshore turnus_slots -> shift_slots; capture template mapping.
- Portion Guidelines & Metrics: direct copy -> portion_guidelines / service_metrics.
- Tasks (prep/freezer): copy into tasks with task_type.
- Messaging: copy to messages.

## Phase 3 – Key Re-Mapping
- Maintain old->new ID map tables temp_dish_map, temp_unit_map for referential rebuild.
- Replace foreign keys in transformed rows using mapping tables.

## Phase 4 – Integrity & QA
- Row counts per domain match +/- expected tolerance (document anomalies).
- Spot check 3 random weeks across tenants.
- Validate no NULL tenant_id or unit_id where required.

## Phase 5 – Cutover
- Disable legacy apps (maintenance banner).
- Run migration script (idempotent, safe to retry).
- Point new unified app at migrated DB.

## Phase 6 – Post Cutover
- Read-only freeze staging tables 30 days, then drop.
- Archive migration logs.

## Rollback Strategy
- If failure before Phase 5 completion: discard target DB, re-enable legacy.
- After Phase 5: maintain dual-run window (read-only legacy) for 48h.
