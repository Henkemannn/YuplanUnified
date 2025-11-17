# Legacy Functional Overview – Kommun (Yuplan3.5) and Offshore (Rigplan1.0)

Purpose: Provide a comprehensive feature inventory with routes, UI screens, data flows, and a mapping/plan for Unified implementation.

## Scope and Sources
- Kommun: `legacy/Yuplan3.5`
  - Core: `app.py`, `templates/`, `static/script.js`, `db/*.sql` tables embedded in code
- Offshore: `legacy/Rigplan1.0`
  - Core: `app.py`, `templates/`, `static/`, `rotation*.py`, `waste.py`, `turnus_*.csv`

---

## Kommun (Yuplan3.5) – Feature Inventory

- Authentication / Session
  - Simple admin and unit login screens (`templates/avdelning_login.html`, admin paths)
- Week View (Personal/Kockvy)
  - Route: `GET /veckovy` → `templates/veckovy.html`
  - UI: Table with 7 days × (Lunch/Kväll), rows: Boende + dietary types; Alt2 lunch highlight; menu popup
  - Actions: cell mark toggle via JS → `POST /registrera_klick`
- Planning (Planera)
  - Route: `GET|POST /planera/<int:vecka>` → `templates/planera.html`
  - Features: select day/meal; choose kosttyper; bulk mark; Alt1/Alt2 planning per day, totals per avdelning
- Admin Panel
  - Route: `GET|POST /adminpanel` → `templates/adminpanel.html` (+ sections)
  - Features: configure kosttyper per avdelning; connect counts; edit boende total/varied per day
- Edit Residents
  - Route: `GET|POST /redigera_boende/<int:avdelning_id>` → `templates/redigera_boende.html`
  - Features: set fixed or per-day counts; forward-propagation to future weeks
- Reports
  - Route: `GET|POST /rapport` → `templates/rapport.html`
  - Views: per-day and per-week summaries (normal vs special), exports (`/export_rapport`)
- Menu Import & Editing
  - Routes: `GET /meny_import`, `POST /upload_meny`, `POST /spara_meny`
  - Data: `veckomeny` table with (vecka, dag, alt_typ, menytext)
- Data Tables (from `app.py`)
  - `avdelningar`, `kosttyper`, `avdelning_kosttyp` (counts per kost)
  - `registreringar` (week/day/meal/kost marked)
  - `boende_antal` (week/day/meal residents overrides)
  - `alt2_markering` (days where Alt2 chosen)
  - `veckomeny` (menu texts alt1/alt2/dessert/kväll)

---

## Offshore (Rigplan1.0) – Feature Inventory

- Public / Common
  - `GET /` (landing/login), `GET /landing`, `GET /coming-soon`
  - Diagnostics: `GET /ping`, `GET /_routes`, `GET /clean`
- Authentication
  - `GET|POST /login`, `/adminlogin`, `/register`
  - Superuser: `GET|POST /superuser`, `/superuser/logout`, `/superuser/panel`, `/superuser/rig/<id>`
- Dashboard & Daily/Weekly Views
  - `GET /dashboard` → `templates/dashboard.html`
  - `GET /week` → `templates/week.html` (weekly schedule/menu)
  - `GET /day_detail` → `templates/day_detail.html`
  - User schedule: `templates/user_schedule.html`
- Menus & Recipes
  - Admin menus: `GET|POST /admin/menu` → `templates/admin_menu.html`, `menus.html`, `menus_overview.html`, `menu_day_form.html`, `menu_detail.html`
  - Recipes: `templates/recipes.html`, `recipe_list.html`, `recipe_detail.html`, `recipe_form.html`
- Planning Hub / Prep
  - Planning hub: `templates/planning_hub.html`, `planning_overview.html`, `planning_dish_detail.html`
  - Prep flows: `templates/week_prep.html`, `prep_upcoming.html`, `prep_modal.html`
- Exports
  - `export_week.html`, `export_shopping.html`, `daily_print.html`
- Turnus (Rotation/Scheduling)
  - Admin: `templates/turnus_admin.html`, `turnus_overview.html`, `turnus_mapping.html`, `turnus_rebind.html`
  - Simulation/engines: `turnus_simple.html`, `turnus_virtual.html`, `superuser_turnusmotor.html`
  - Data helpers: `rotation.py`, `rotation_simple.py`, CSV mapping
- Admin / Settings
  - `templates/admin_dashboard.html`, `admin_users.html`, `settings.html`, `messages.html`

Note: Rigplan routes are numerous; above are grouped by template presence and representative route matches in `app.py`.

---

## Cross‑Cutting UX Patterns
- iPad‑first, table‑centric weekviews; clear Lunch/Kväll distinction
- Alt1/Alt2 choices and highlights (Kommun); popup with menu details
- Print‑friendly views across both (week, daily prints, exports)
- Simple, direct actions with minimal modals; clear labels and big hit areas

---

## Unified Mapping (High Level)

- Tenancy & Users → Unified `Tenant`, `User`, roles (`superuser`, `admin`, `cook`, `viewer`)
- Units/Departments → Unified `Unit`
- Dietary Types & Assignments → `DietaryType`, `UnitDietAssignment`
- Weekview Registrations → `weekview_registrations` (Unified WeekviewRepo)
- Residents Counts → `weekview_residents_count`
- Alt2 Flags → `weekview_alt2_flags` or Admin Alt2 APIs
- Menus & Variants → `Menu`, `MenuVariant` (alt1/alt2/dessert/kvall)
- Recipes/Tasks/Exports → map progressively to Unified models/services
- Scheduling (Turnus) → future Unified module (templates + API for templates/slots)

Existing Unified APIs
- Weekview (read + mutations): `GET /api/weekview`, `PATCH /api/weekview`, `/weekview/residents`, `/weekview/alt2`
- Admin Alt2 (Pass B): `GET/PUT /admin/menu-choice` (department/week/day)
- Imports, Reports, Metrics, Notes, Service metrics (existing modules)

Gaps to Close
- Weekview `menu_texts` in payload for popup (Unified currently lacks embedded menu texts)
- Department names and diet labels in `GET /api/weekview` response for direct rendering
- Rigplan prep/recipes/routes need alignment with Unified recipe/dish models
- Turnus engine & UI (port or redesign) as a dedicated Unified module

---

## Implementation Plan (Phased)

Phase A – Kommun Weekview Parity (Read‑only)
- Backend: extend `GET /api/weekview` to include `menu_texts` (mon..sun × alt1/alt2/dessert/kvall)
- UI: `/ui/weekview` table, iPad‑optimized, Alt2 highlights, popup, print CSS
- Navigation: week prev/next + picker, department dropdown

Phase B – Kommun Mutations
- PATCH toggles for marks (`/api/weekview`), residents (`/weekview/residents`), Alt2 days (`/weekview/alt2`) with If‑Match + CSRF
- Handle 412 gracefully with refetch + retry

Phase C – Admin / Imports / Reports
- Menu import editor parity; admin panel for kosttyp counts & connections
- Reports UI (week/day summaries) using Unified data

Phase D – Offshore Foundations
- Menus/recipes CRUD and overview pages mapped to Unified models/APIs
- Prep lists (week_prep, upcoming) driven by menu + residents
- Exports: week and shopping list endpoints

Phase E – Turnus (Rotation)
- Define Unified scheduling models (templates, slots)
- Import adapters from Rigplan CSV/logic; implement overview/admin pages

---

## Priorities (Must / Should / Could)
- Must (Kommun v1): Read‑only weekview with popup + iPad UI + print
- Must (Kommun v2): Mutations with ETag/CSRF (marks, residents, Alt2)
- Should: Admin kosttyp connections, menu import basics, reports summaries
- Could: Offline cache, sticky headers, keyboard shortcuts, compact card view
- Future (Offshore): Menus/recipes/prep parity; Turnus MVP; exports

---

## Acceptance Checklist (Kommun v1)
- `/ui/weekview` renders table correctly for chosen department/week
- Alt2 lunch highlighting matches backend `alt2_days`
- Menu popup shows Alt1/Alt2/Dessert/Kväll when available
- `If-None-Match` honored (304 when unchanged)
- Works well on iPad (1024×768), clean print view

## Acceptance Checklist (Kommun v2)
- Cell toggles and residents edits persist via PATCH (with If‑Match)
- Alt2 day updates persist; weekend policy enforced where applicable
- ETag conflicts handled with user‑friendly retry
