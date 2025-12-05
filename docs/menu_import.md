# Unified Admin – Menu Import Phases 7–12

This document describes the Admin Menu Import UI behavior across phases 7 through 12 and the final stabilized flows.

## Phase 7 – Upload & Placeholder
- CSV upload form available at `/ui/admin/menu-import`.
- Accepts `.pdf` files as placeholders (used for early demos). Shows a success flash: "Menyfil '<name>' mottagen (implementeras senare)."
- Upload with no file shows error flash: "Ingen fil vald."

## Phase 8 – CSV Parsing & Validation
- Only `.csv` files are parsed and imported. Non-CSV formats (e.g., `.txt`) are rejected with error flash: "Ogiltigt menyformat eller saknad fil."
- CSV parsing converts rows into weeks and menu variants. Import summary flash:
  - "Menyn importerad: <created> skapade, <updated> uppdaterade, <skipped> hoppade över (<weeks> veckor)."

## Phase 9 – Week Edit/Save
- Week view and edit at `/ui/admin/menu-import/week/<year>/<week>`.
- Save route `/ui/admin/menu-import/week/<year>/<week>/save` centralizes logic in the Admin blueprint; UI route delegates.
- Behavior:
  - Trims text inputs.
  - Empty fields result in `NULL` dish_id (clears variant).
  - Upserts dishes by name (create if missing, reuse if existing).
  - Updates or creates `MenuVariant` per day/meal/variant-type.
  - Bumps `menus.updated_at`.
  - Shows success flash: "Menyn uppdaterad (<N> ändringar sparade)."

## Phase 10 – Publish/Unpublish
- Publish: `/ui/admin/menu-import/week/<year>/<week>/publish` sets status to `published`.
- Unpublish: `/ui/admin/menu-import/week/<year>/<week>/unpublish` sets status to `draft`.
- Success flashes: "Vecka <week> publicerad." / "Vecka <week> satt till utkast."

## Phase 11/12 – ETag & Conflict Flows
- GET week includes `ETag` header (weak, includes `menu_id` + timestamp).
- Edit view includes hidden `_etag` field.
- Save requires correct ETag when provided; conflicts produce a flash:
  - "Konflikt: <detail> Ladda om sidan för att se senaste versionen."
- Concurrent edit scenario supported: stale ETag triggers conflict.
- Admin handler enforces ETag; UI route performs optional validation and delegates to Admin handler.

## POST /save – Form Fields
Inputs follow the pattern `<Day>_<Meal>_<Variant>` with Swedish day names and meal labels:
- Days: `Måndag`, `Tisdag`, `Onsdag`, `Torsdag`, `Fredag`, `Lördag`, `Söndag`
- Meals: `Lunch`, `Kväll`
- Variants: `alt1`, `alt2`, `dessert`, `kvall`

Example:
```
_Måndag_Lunch_alt1 = "Köttbullar"
_Måndag_Lunch_alt2 = "Fiskgratäng"
_Måndag_Lunch_dessert = "Glass"
_Måndag_Kväll_kvall = "Mackor"
```

## Determinism & UI Stabilization (Related)
- Weekly Report `/ui/reports/weekly` accepts `site_id` and deterministically selects site when absent.
- Admin Departments: title vs H1 copy aligned; empty-state strings present consistently.

## Notes
- UI save route delegates to Admin save to avoid duplicate logic and ensure consistent ETag enforcement.
- Non-CSV handling is nuanced: `.pdf` allowed for demo (Phase 7), others rejected (Phase 8).
