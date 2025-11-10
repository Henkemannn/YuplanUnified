# Legacy Inventory — Offshore

This document inventories the legacy Offshore application to inform the Unified Platform migration.

## Overview

- Framework: Flask + SQLite
- Key domains: Menus, Planning hub, Turnus (rotation), Recipes, Prep tasks & Freezer items, Daily/weekly exports, Messaging, Admin & Superuser panels, Auth
- Blueprints: inline routes; a separate waste/service blueprint (`waste.py`) registered under `/service` (not detailed here)

## Route map (grouped)

Auth & landing
* / [GET|POST] — Root (login/redirect)
* /login [GET|POST], /register [GET|POST], /logout [GET]
* /adminlogin [GET|POST], /admin [GET], /admin/dashboard [GET]
* /superuser [GET|POST], /superuser/logout [GET], /superuser/panel [GET|POST], /superuser/rig/<id> [GET|POST]
* /health [GET], /ping [GET], /favicon.ico [GET]

Utilities
* /_routes [GET] — List route map (JSON)
* /landing [GET], /clean [GET], /coming-soon [GET]

Planning & menus
* /planning [GET], /planning/overview [GET], /planning/dish/<id> [GET]
* /admin/menu [GET|POST], /admin/menu/upload [POST], /admin/menu/update [POST]
* Daily menus: /menus/daily_docx [GET], /menus/daily_print [GET], /menus/daily/update [POST], /menus/daily/reset [POST], /menus/daily/get [GET], /menus/daily/bulk_update [POST]
* Public: /public/menus [GET]
* Import: /menus/import_menu_file [POST], /menus/import_rotation [POST]
* Export: /export/week/<int:work_cycle_id> [GET], /export/shopping/<int:work_cycle_id> [GET]

Recipes
* /recipes [GET], /recipes/new [GET|POST], /recipes/<id> [GET], /recipes/<id>/edit [GET|POST]
* /dish/<id>/link_recipe [POST]

Calendar & day/week
* /me/calendar [GET], /me/schedule [GET]
* /day/<date> [GET], /day/note [GET|POST], /week/<date> [GET], /period/<date>/aggregate [GET]

Prep tasks & freezer
* /prep/upcoming [GET], /prep/tasks [GET]
* /prep/tasks/add [POST], /prep/tasks/toggle [POST], /prep/status/batch [POST]
* /frys/items [GET], /frys/items/add [POST], /frys/items/toggle [POST]

Turnus (rotation)
* /turnus/admin [GET], /turnus/simple [GET]
* /turnus/simple/build_base [POST], /turnus/simple/apply [POST]
* /turnus/virtual [GET], /turnus/overview [GET]
* /turnus/mapping [GET|POST], /turnus/rebind [GET|POST]
* /turnus/create_real_cooks [GET|POST], /turnus/preview [GET], /turnus/view [GET]

Messaging
* /messages [GET], /messages/admins [GET]
* /messages/post_bulletin [POST], /messages/send_direct [POST], /messages/send_daily_menu [POST]
* /downloads/daily_menu/<filename> [GET]

Service metrics (via waste blueprint)
* /service/* — not exhaustively listed here

## Templates (selection)

- admin_layout.html, admin_dashboard.html, admin_menu.html, admin_users.html
- layout.html, dashboard.html, planning_hub.html, planning_overview.html, calendar.html, day_detail.html
- menus.html, menus_overview.html, menu_day_form.html, menu_detail.html
- recipes.html, recipe_list.html, recipe_form.html, recipe_detail.html
- turnus_admin.html, turnus_simple.html, turnus_overview.html, turnus_mapping.html, turnus_rebind.html, turnus_virtual.html
- period_aggregate.html, export_week.html, export_shopping.html
- messages.html, _admin_sidebar.html, settings.html, register.html, login.html, superuser_*.

## Data model (selection)

- Core tables created lazily: users, rigs
- Menu catalog and mapping:
  - dish_catalog(rig_id, slug, name, recipe_id, ...)
  - menu_dish_map(rig_id, menu_index, weekday, meal, category, dish_id)
- Recipes: recipes(..., categories, method_type, base_portions, raw_text)
- Prep tasks: prep_tasks_private(..., date, meal, category, text, done, dish_id)
- Freezer items: frys_items_private(..., qty, unit, dish_id)
- Service metrics: service_metrics(..., date, meal, category, guest_count, produced/served/leftover)
- Various settings: menu_settings(start_week, start_index, menu_json)

## Feature notes

- Planning hub + daily/weekly views with category buckets (soppa/fisk/kött/extra)
- Menu import from CSV/rotation; exports (DOCX daily, HTML/PDF-like, CSV shopping/week)
- Recipe management with linking between dishes and recipes
- Prep/private tasks and freezer inventory per user/rig/date/meal/category
- Turnus: build/apply rotations across cooks; admin workflows for mapping/rebinding
- Messaging: bulletin/direct and daily menu distribution to admins

## Risks / quirks

- Heavy inline SQL; migrations implied rather than explicit
- No ETag/If-Match; no RFC7807; minimal RBAC beyond session role checks
- Large monolithic app.py (~5k LOC) with many responsibilities
