# Unified Mapping — Legacy to Unified Platform

This document maps legacy features/endpoints to their Unified Platform counterparts, with migration notes.

## Admin

- Legacy (Kommun):
  - /meny_avdelning_admin — edit menu text (Alt1/Alt2), set Alt2 flags across departments/weeks
  - Data: avdelningar, kosttyper, avdelning_kosttyp, veckomeny, alt2_markering
- Unified:
  - /api/admin/sites [POST 501] — Phase A placeholder
  - /api/admin/departments [POST 501], /api/admin/departments/{id} [PUT 501]
  - /api/admin/departments/{id}/diet-defaults [PUT 501]
  - /api/admin/alt2 [PUT 501] — bulk week-level Alt2
  - /api/admin/stats [GET] — summary stats with ETag/304
  - Notes: All writes gated for Phase A (501). Phase B provides persistence + If-Match semantics.

## Weekview & Planning

- Legacy (Kommun):
  - /veckovy [GET] — per-department meal breakdown; Alt2 highlight at lunch
  - /planera/<vecka> [GET|POST] — select Alt1/Alt2 dish and specialkost per kosttyp
  - /redigera_boende/<id> [GET|POST] — edit residents
- Unified:
  - /api/weekview [GET, PATCH] — read view and apply granular operations (If-Match)
  - /api/weekview/residents [PATCH] — set counts (If-Match)
  - /api/weekview/alt2 [PATCH] — mark Alt2 days (If-Match)
  - Notes: GET defined; PATCH endpoints outlined with ETag requirements.

## Reports

- Legacy (Kommun):
  - /rapport [GET|POST], /export_rapport [POST] — summarize and export
- Unified:
  - /api/report [GET], /api/report/export [GET] — read-only with conditional GET

## Menus & Import

- Legacy:
  - Kommun: /meny_import, /upload_meny, /spara_meny — UI-driven menu text per day (Alt1/Alt2)
  - Offshore: /admin/menu [GET|POST], /menus/import_menu_file [POST], /menus/import_rotation [POST]
- Unified:
  - /import/csv|/docx|/xlsx [POST]
  - /import/menu [POST] — minimal JSON example present
  - Notes: Additional transforms needed for legacy formats.

## Alt1/Alt2

- Legacy (Kommun): alt2_markering per department/day/week; veckomeny stores menu text for Alt1/Alt2
- Unified: /api/weekview/alt2 [PATCH] and /api/admin/alt2 [PUT] bulk (501 in Phase A)

## Out of scope (for now)

- Offshore: Recipes (/recipes/*), Turnus (/turnus/*), Messaging (/messages/*)
  - Can be considered as future optional modules after core migration.

## Mapping table (examples)

| Legacy Endpoint | Unified Endpoint | Notes |
|---|---|---|
| kommun:/veckovy | /api/weekview [GET] | Read-only mapping; add tenant/department filters |
| kommun:/planera/<vecka> | /api/weekview/alt2 [PATCH], /api/weekview [PATCH] | Requires ETag + operation schema |
| kommun:/redigera_boende/<id> | /api/weekview/residents [PATCH] | If-Match enforcement |
| kommun:/meny_import, /upload_meny | /import/menu [POST] | Normalize payloads |
| kommun:/rapport, /export_rapport | /api/report, /api/report/export | Add 304 support |
| offshore:/admin/menu/* | /import/menu | Admin UI maps to import service |
| offshore:/public/menus | N/A (public) | Consider static export if needed |
# Unified mapping: Legacy → Unified (Weekview / Report / Admin)

Scope: municipal and offshore modules present in this workspace. Timeboxed, minimal breadth.

## Weekview
- Legacy (Kommun/Offshore): No weekview endpoints found in `modules/municipal` or `modules/offshore`.
- Unified:
  - GET `/api/weekview` (ETag + 304)
  - PATCH `/api/weekview`
  - PATCH `/api/weekview/residents`
  - PATCH `/api/weekview/alt2`
  - Flag: `ff.weekview.enabled`

## Report
- Legacy (Kommun/Offshore): No report endpoints found in `modules/municipal` or `modules/offshore`.
- Unified:
  - GET `/api/report` (read-only; ETag + 304)
  - Flag: `ff.report.enabled`

## Admin foundations
- Legacy (Kommun/Offshore): No admin endpoints found in these modules.
- Unified:
  - Admin feature flags and audit APIs exist under `core/admin_api.py` and `core/admin_audit_api.py`.

## Templates → UI
- Legacy municipal/offshore modules do not include templates in this workspace snapshot for these areas.
- Unified UI is structured under `templates/` (see `_base.html`) and inline UI (`core/inline_ui.py`). For Weekview/Report UX, mapping occurs at API level and is consumed by modern clients.
