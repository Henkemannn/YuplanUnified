# Weekview Phase 2.D — Site Overview Specialdiets (Read-only)

## Scope

Phase 2.D adds special-diet outcome data to the site-level Weekview overview UI:

- Weekly aggregates per department
- Per-day indicators when any diet is marked
- No mutations or interactions in this phase
- Fully read-only

## Key changes

### Controller / View Model
- Aggregates marked diets per department:
  - `weekly_diets`: list of `{diet_name, total_marked_count}`
  - Only includes diet types with non-zero totals
- Computes per-day flags:
  - `has_marked_diets = True` if any diet is marked in lunch/dinner

### Template (`weekview_overview.html`)
- New “Specialkost (vecka)” column
- Compact `diet-summary-pill` items (e.g. `Gluten: 4`)
- Subtle per-day `.diet-dot` marker in the 7-day strip

### Stability fixes
- `db.py`: Added `get_new_session()`; prevents accidental closure of the thread-scoped session used by other parts of the app
- `menu_service.py`: Updated `create_or_get_menu`, `set_variant`, and `get_week_view` to use `get_new_session()` to avoid detached instances
- `weekview.html`: Simplified diet label rendering to match existing UI tests
- `weekview_overview.html`: Removed inline `.alt2-gul` CSS that inflated class count in tests

## Tests
- Added: `tests/ui/test_weekview_site_overview_diets_phase2d.py`
  - Verifies weekly aggregates (`Gluten: 4`, `Laktos: 1`)
  - Verifies `.diet-dot` where expected
  - Ensures “Ingen specialkost registrerad” only appears when applicable
- Entire suite: `361 passed, 7 skipped, 3 warnings`

## No behavior changes outside Weekview
- No API modifications
- No changes to Weekview department UI
- No mutations added to overview
