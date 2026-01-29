# Inventering: Kockpilot (Registrering, Planering, Utskrift, Data)

Syfte: Läs-only inventering av befintliga flöden som kan återanvändas i kockpilotens första steg. Inga kodändringar.

## Registrering (Veckovy/Avdelning)
- Veckovy UI: templates/ui/unified_weekview.html
  - Klickbara måltidsceller (lunch/kväll) med inline toggle och modal "Registrera måltid".
  - Dietpiller för specialkost (klass `diet-pill`) med data-attribut (kosttyp, dag, måltid, vecka/år, avdelning).
- JS-hantering: static/js/unified_weekview.js
  - Dietpill-klick: hämtar ETag via GET /api/weekview/etag och POST:ar till /api/weekview/specialdiets/mark (optimistisk UI + If-Match).
  - Inline-toggle av registrering skickar form direkt; modal för explicit toggling/spar.
  - Tangentbordsstöd (pilar, Enter/Space) och toast-feedback.
- API (UI blueprint): core/ui_blueprint.py
  - GET /api/weekview/etag: returnerar aktuell ETag för avdelning/vecka (WeekviewRepo.get_version → WeekviewService.build_etag).
  - POST /api/weekview/specialdiets/mark: markerar diet per dag/måltid med ETag-kontroll (412 vid konflikt) och säkerställer site-isolering.
  - GET /ui/register/meal: enkel registreringsvy per dag/måltid för en avdelning.
- Persistens:
  - Specialkostmarkeringar: tabell `weekview_registrations` (tenant, department, year/week, dagindex, meal, diet_type, marked).
  - ETag-versioner: `weekview_versions` (per avdelning/vecka), bumpas vid ändringar.
  - Boendeantal per måltid: `weekview_residents_count` (lunch/kväll per dag).
  - Måltidsregistreringar (ack/kvittens): `meal_registrations` (site, avdelning, datum, måltid, registered) via MealRegistrationRepo.

## Planering (Alt2 per avdelning/dag)
- Adminvy och rutter: core/ui_blueprint.py
  - GET /ui/admin/menu-planning: Veckoväljare.
  - GET /ui/admin/menu-planning/week/<year>/<week>: Översikt per avdelning/dag med Alt2-badge.
  - GET /ui/admin/menu-planning/week/<year>/<week>/edit: Form med checkboxar per avdelning/dag.
  - POST /ui/admin/menu-planning/week/<year>/<week>/edit: Sparar Alt2-val för veckan.
- Templates:
  - templates/ui/admin_menu_planning_index.html
  - templates/ui/admin_menu_planning_view.html
  - templates/ui/admin_menu_planning_edit.html
- Persistens:
  - Alt2-flaggor: `weekview_alt2_flags` (site, department, year/week, day_of_week, enabled). Canonisk site-scoped schema; repo migrerar äldre schema.
  - Repo: core/menu_planning_repo.py (hämtar/sätter Alt2 per vecka/site).

## Utskrift och Export
- Veckorapport (PDF): GET /ui/reports/weekly.pdf i core/ui_blueprint.py
  - Genererar print-vänlig HTML via templates/ui/unified_report_weekly_print.html; skriver minimal, giltig PDF-bytes.
- Veckorapport (XLSX): GET /ui/reports/weekly.xlsx (samma modul) med enkel tabell-export.
- Veckorapport (HTML): templates/ui/unified_report_weekly.html (administratörsväg-länkad).

## Data & Modeller
- WeekviewRepo: core/weekview/repo.py
  - Skapar/garanterar testvänliga tabeller (`weekview_registrations`, `weekview_versions`, `weekview_residents_count`, `weekview_alt2_flags`).
  - Hämtar veckovy-data, versioner och Alt2 (site-scoped). Bump av version vid toggles/spar.
- MealRegistrationRepo: core/meal_registration_repo.py
  - Hämtar och upsertar `meal_registrations` (dag/måltid) med `updated_at` för enklare spårning.
- Avdelning – veckoboendeantal (admin): admin/ui_blueprint.py
  - `department_residents`: (tenant, site, department, date, meal_type, count) – UI för veckovis redigering (Mon–Sun × Lunch/Kväll).

## Relaterade vyer (Kock/Portal)
- Enhetsportal – veckovy: core/ui_blueprint.py → unified_portal_week.html
  - Visar meny per dag, registreringsstatus, Alt2-badge, dietdefaults och länkar till Planera per dag.
- Kock – veckogrid: GET /ui/kitchen/week i core/ui_blueprint.py
  - Grid-läge med rader per kosttyp och celler per dag/måltid; återanvänder WeekviewService och måltidsregistreringar.
- Kock – översikt (Alt2): unified_cook_week_overview.html visar Alt2-närvaro per dag.

## Återanvändningspotential (pilot)
- Dietpill-toggles (ETag + optimistisk UI): HÖG – stabil API och UI.
- Planering Alt2 (adminvy + repo): MEDEL – komplett men kan kräva UI-polish.
- Registreringsmodal/inline (veckovy): HÖG – tydlig och testad interaktion.
- Utskrift/Export (PDF/XLSX): MEDEL – funktionell, enkel layout; kan byggas ut.
- Datamodeller (WeekviewRepo + MealRegistrationRepo): HÖG – väl definierade tabeller och versionering.

## Vägledande "One True Path" (pilot)
- Menyimport: använd /ui/admin/menu-import* (CSV/DOCX) och MenuServiceDB. Legacy /import/* är frysta under pilot.
- Menyvisning: konsumera via /menu/week och veckovy/portalvyer; undvik legacy/generisk import i pilotens flöden.

## Nästa steg (utan kodändringar)
- Konvergera kockvy mot befintlig veckogrid och dietpillflöde.
- Addera länkade arbetsflöden: Planera (dag) från veckovy för lunch.
- Utvärdera behov av printvänliga vyer för kök (dag/vecka) ovanpå befintlig PDF/XLSX.
