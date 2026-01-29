# Duplicates & Legacy (Pilot Freeze — DEV/LEGACY paths)

Pilot Freeze Rules
- Explicitly DEV/LEGACY (do not modify during pilot fixes):
  - /import/menu
  - /import/docx
  - Any generic import APIs not wired to Admin UI
- Note: These paths are intentionally not part of the pilot flow. They must not be modified during pilot fixes unless a consolidation task is explicitly approved.

- Endpoint: /import/docx
  - Module: [core/import_api.py](../core/import_api.py) `import_docx()` → [core/importers/docx_table_importer.py](../core/importers/docx_table_importer.py)
  - Status: DEV/LEGACY (generic import API; not used by Admin menu import UI)
  - Why: No template/link references; separate format rows, not DB menu writes

- Endpoint: /import/menu
  - Module: [core/import_api.py](../core/import_api.py) `import_menu()`
  - Status: DEV/LEGACY (tests-only harness)
  - Why: Commented as legacy; relies on monkeypatch; not linked from UI

- Importer: `DocxMenuImporter`
  - Module: [core/importers/docx_importer.py](../core/importers/docx_importer.py)
  - Status: USED
  - Why: Called by [admin/ui_blueprint.py](../admin/ui_blueprint.py) `admin_menu_import_upload()` for DOCX uploads

- Template: Weekview Overview
  - File: [templates/ui/weekview_overview.html](../templates/ui/weekview_overview.html)
  - Status: USED
  - Why: Rendered by [core/ui_blueprint.py](../core/ui_blueprint.py) `weekview_overview` routes for site-level summaries

- Portal Kitchen Grid Menu Popup
  - Files: [templates/unified_portal_week.html](../templates/unified_portal_week.html), [static/unified_portal.js](../static/unified_portal.js)
  - Status: USED (separate portal UI)
  - Why: Route [core/ui_blueprint.py](../core/ui_blueprint.py) `portal_week()` renders; distinct from weekview modal

- API Day-Label Translation
  - Module: [core/menu_api.py](../core/menu_api.py) `_legacy_day_label()`
  - Status: USED
  - Why: Keeps Mon/Tue/Wed labels for legacy API clients; client modal canon now handles mixed keys

- Notes:
- Do not touch during pilot: All DEV/LEGACY items above, unless explicitly migrated with approval.
- Unknowns for Henrik:
  - Is /import/docx intended for any admin workflow, or keep as developer/testing utility?
  - Should we eventually unify DOCX parsing under one importer (admin UI vs generic import API), or keep separate?
