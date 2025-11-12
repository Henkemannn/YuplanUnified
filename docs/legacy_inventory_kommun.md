# Legacy Inventory — Kommun

This document inventories the legacy Kommun application to inform the Unified Platform migration.

## Overview

- Framework: Flask + SQLite
- Key domains: Departments (avdelningar), Diet types (kosttyper), Week view (veckovy), Planning (planera), Reports (rapport), Menu text per day/Alt1/Alt2 (veckomeny), Alt2 flags (alt2_markering)
- Storage tables (created if missing):
  - avdelningar, kosttyper, avdelning_kosttyp, registreringar, boende_antal, alt2_markering, veckomeny

## Routes (endpoints)

Legend: [GET], [POST], [GET|POST]

- / [GET] — Landing/index
- /admin [GET|POST] — Admin dashboard + login/change password
- /byt_losenord [POST] — Change password (admin)
- /avdelning_login [GET|POST] — Department login
- /menyval [GET|POST] — Staff view to review weekly menu and Alt2 selections
- /meny_avdelning_admin [GET|POST] — Admin for menu text (Alt1/Alt2) and Alt2 flags per department/week
- /adminpanel [GET|POST] — Admin panel (combined operations)
- /veckovy [GET] — Week view rendering (per department/meal with Alt2 highlight)
- /planera/<vecka> [GET|POST] — Planning page (Alt1/Alt2 anrättning + specialkost selection)
- /redigera_boende/<avdelning_id> [GET|POST] — Edit resident counts per day/meal
- /rapport [GET|POST] — Report/statistics view (summaries and totals)
- /export_rapport [POST] — Export report to Excel (xlsx)
- /meny_import [GET] — Menu import UI
- /upload_meny [POST] — Upload menu data
- /spara_meny [POST] — Save menu for week/day/Alt1/Alt2
- /veckovy_redirect, /planera_redirect [GET] — Convenience redirects
- /registrera_klick [POST] — Register toggle click (marking)

## Templates

- base.html, base_new.html, index.html, index_new.html, admin.html, adminpanel*.html, avdelning_login.html
- menyval.html, meny_avdelning_admin.html, meny_import.html
- veckovy.html, planera.html
- rapport.html, redigera_boende.html

## Models (SQLite tables)

- avdelningar(id, namn, boende_antal, faktaruta)
- kosttyper(id, namn, formarkeras)
- avdelning_kosttyp(avdelning_id, kosttyp_id, antal)
- registreringar(vecka, dag, maltid, avdelning_id, kosttyp_id, markerad)
- boende_antal(avdelning_id, dag, maltid, antal, vecka)
- alt2_markering(avdelning_id, dag, vecka)
- veckomeny(vecka, dag, alt_typ, menytext)

## Helpers (selection)

- ensure_database() — idempotent DB/table creation
- get_db_connection() — SQLite connection with migrations for veckomeny/alt2_markering
- Export helpers: /export_rapport builds XLSX (OpenPyXL)
- Alt2 utilities: compute/set flags and derive counts for specialkost vs normal

## Feature notes

- Admin creation & department logic: simple admin panel; departments stored in avdelningar
- Weekview rendering: derives per-day/meal counts; highlights Alt2 at lunch
- Report/statistics: summarizes normal/special per day and totals; Excel export
- Menu import & storage: UI/forms to upload and persist per-day Alt1/Alt2 text
- Alt1/Alt2 handling: alt2_markering per department/day/week; menu text per day with alt_typ

## Risks / quirks

- Direct SQL and implicit migrations inside request path
- No ETag/If-Match; no RFC7807; limited RBAC/session checks
- Alt2 only linked to Lunch in several computations
