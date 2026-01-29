# Ground Zero: GZ-P0.26.4-modal-daykeys

Pilot One True Path (rules)
- Current Ground Zero: GZ-P0.26.4-modal-daykeys
- Menu import/publish: ONLY via /ui/admin/menu-import/*
- Menu read: ONLY via /menu/week
- Weekview rendering: weekview_all.html + weekview_menu_modal.js
- When fixing pilot bugs:
	- Do NOT touch /import/* endpoints unless explicitly instructed
	- If multiple paths exist, STOP and ask before changing anything

## A) Menu Import/Publish (DOCX upload)
- Entry URLs: /ui/admin/menu-import (GET); /ui/admin/menu-import/upload (POST); /ui/admin/menu-import/week/<year>/<week>/publish (POST)
- Handler: core/ui_blueprint.py: `admin_menu_import_list()`, `admin_menu_import_upload()` → delegates to [admin/ui_blueprint.py](../admin/ui_blueprint.py) `admin_menu_import()`, `admin_menu_import_upload()`; publish via `admin_menu_import_week_publish()`
- Services: `MenuImportService`, `MenuServiceDB`; DOCX via `core/importers/docx_importer.DocxMenuImporter`; CSV via `core.menu_csv_parser.parse_menu_csv` + `csv_rows_to_import_result`
- DB Tables: `menus`, `menu_variants`, `dishes`

## B) Menu Read (Weekview Modal)
- Entry URL: /menu/week
- Handler: [core/menu_api.py](../core/menu_api.py) `get_week()` → uses `current_app.menu_service.get_week_view()`
- Day-Key Normalization: client-side in [static/weekview_menu_modal.js](../static/weekview_menu_modal.js) (`normalizeDayKey()` + lookup); server translates `mon..sun` → `Mon..Sun` when applicable
- Caching (client): in-page `cachedMenu` (memoized fetch per page/session)
- Services: `MenuServiceDB.get_week_view()`
- DB Tables: `menus`, `menu_variants`, `dishes`

## C) Weekview Rendering
- Entry URL: /ui/weekview
- Handler: [core/ui_blueprint.py](../core/ui_blueprint.py) `weekview_ui()`
- Template: [templates/ui/weekview_all.html](../templates/ui/weekview_all.html) for site-wide view; [templates/ui/unified_weekview.html](../templates/ui/unified_weekview.html) for single department
- Static JS: [static/weekview_menu_modal.js](../static/weekview_menu_modal.js), [static/unified_ui.js](../static/unified_ui.js)
- Services: `WeekviewService.fetch_weekview()` + [core/weekview/repo.py](../core/weekview/repo.py); site-level menu-days presence via `MenuServiceDB.get_week_view()`
- DB Tables: `weekview_registrations`, `weekview_versions`, `weekview_residents_count`, `weekview_alt2_flags`, plus `departments`, `sites`; reads `menus`, `menu_variants`, `dishes` for site menu-days summary

## D) Admin “Meny & registrering”
- Entry URL: /ui/admin/menu-import (nav in [templates/ui/unified_admin_base.html](../templates/ui/unified_admin_base.html))
- Handlers: [core/ui_blueprint.py](../core/ui_blueprint.py) `admin_menu_import_list()` → [admin/ui_blueprint.py](../admin/ui_blueprint.py) `admin_menu_import()`; upload/list/week edit/save/publish via same admin module
- “Importerade menyer” list: DISTINCT `year, week` from `menus` in `admin_menu_import()`
- DB Tables: `menus`, `menu_variants`, `dishes` (ETag uses `Menu.updated_at`)
