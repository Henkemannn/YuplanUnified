# Weekview Phase 1 — API Enrichment (Read-only)

Summary
- Enriches `GET /api/weekview` to return a complete `days[]` array per department for Phase 1 UI.
- Adds menu texts (lunch/dinner, alt1/alt2, dessert optional), per-day Alt2 flag, and resident counts, while preserving existing fields. ETag semantics unchanged.

Why
- The Weekview UI (Kommun) needs a single GET to render the full week, iPad-first. See `docs/weekview_unified_proposal.md` and `docs/weekview_api_schema.md`.

Changes
- core/weekview/service.py
  - Added server-side enrichment building `department_summaries[].days[1..7]` with:
    - `day_of_week`, `date` (ISO), `weekday_name`
    - `menu_texts.lunch.alt1|alt2|dessert` (when present)
    - `menu_texts.dinner.alt1|alt2` (when present)
    - `alt2_lunch` boolean (mirrors `alt2_days`)
    - `residents.{lunch,dinner}` (aggregated from existing `residents_counts`)
  - Sources:
    - Menu texts via `current_app.menu_service.get_week_view(tenant_id, week, year)`
    - Existing Weekview aggregates from repo
  - Backwards-compatible: `marks`, `residents_counts`, `alt2_days` preserved; `days[]` is additive.
  - ETag unchanged: still `W/"weekview:dept:<dep>:year:<yyyy>:week:<ww>:v<version>"` and used for If-None-Match 304.
- docs/weekview_api_schema.md
  - New: example response and field reference for enriched `GET /api/weekview`.
- docs/weekview_unified_proposal.md
  - Added link to the API schema doc.
- tests/weekview/test_weekview_phase1_payload.py
  - Integration-style API test seeding menu, alt2, and residents; verifies `days[]` fields and ETag.

Notes
- Dinner fields are kept in payload (no feature flag). UI will render dinner columns only if any dinner data exists for the week.
- Menu text changes do not currently affect the Weekview ETag; ETag continues to reflect Weekview registration/resident/alt2 changes. We can revisit when menu editing ties into weekview versioning.

CI
- CI uses Python 3.11 (`.github/workflows/ci.yml`), runs pytest on Postgres and SQLite. Local Python 3.14 incompatibilities are not relevant to CI.

Testing
- Verified new test covers Phase 1 fields and conditional GET semantics.
- Expectation: Full suite remains green in CI; if any regressions surface, I’ll follow up in this PR.

Mapping to UI
- The UI will consume:
  - Header: `year`, `week`, (department/site names resolved by UI route)
  - Table rows: `department_summaries[0].days[*]` → `weekday_name`, `date`, `menu_texts` (lunch/dinner alt1/alt2/dessert), `alt2_lunch`, `residents.{lunch,dinner}`
  - Legacy fields are available if needed for diet rows: `marks`, `residents_counts`, `alt2_days`.

Closes
- Phase 1 API readiness for Weekview UI (Kommun).
