# Copilot Instructions / Context Bootstrap

This file gives the AI assistant (Copilot) the full context needed to continue implementing the unified Yuplan platform without re-reading legacy repos.

## 1. Mission
Merge two legacy Flask+SQLite apps (Municipal & Offshore) into a single multi-tenant, modular platform. Core provides menus, diets, attendance, users, tenants, import/export. Optional modules add: turnus scheduling, waste metrics, prep/freezer tasks, messaging, alt1/alt2 workflow.

## 2. Current State (Scaffold Complete)
Implemented:
- App factory (`core/app_factory.create_app`)
- Config + feature flags (in-memory)
- SQLAlchemy model skeletons (see `core/models.py`)
- DB engine & session (`core/db.py`)
- Service interface stubs (`core/services.py`)
- Module blueprints: `municipal`, `offshore` (ping endpoints)
- Documentation: architecture, data model, modules, migration plan, roadmap, deployment
- Alembic scaffold (no initial migration generated yet)
- Runner (`run.py`)

## 3. Domain Summary
Core Domains:
- Tenants / Units / Users
- Menus (week/year + variants alt1/alt2/dessert/kvall)
- Menu Overrides (scope: global, unit, private future)
- Dietary Types & UnitDietAssignments
- Attendance (unit/day/meal with origin semantics)
- Tasks (generic base; modules specialize)
- Export/Import adapters (planned)

Offshore Module Adds:
- Scheduling (turnus) via ShiftTemplate + ShiftSlot
- Waste Metrics (PortionGuideline + ServiceMetric + recommendation algorithm)
- Tasks (prep/freezer) types
- Messaging (Message)

Municipal Module Adds:
- Alt1/Alt2 workflow (just specific variant logic + UI layer)
- Diet selection view semantics reused from core tables

## 4. Feature Flags (Seed)
```
menus, diet, attendance,
module.municipal, module.offshore,
turnus, waste.metrics, prep.tasks, freezer.tasks, messaging,
export.docx, import.docx
```
Later: persistent per-tenant toggles.

## 5. Immediate Next Implementation Tasks (Recommended Order)
1. Generate Alembic initial migration: reflect `core/models.Base.metadata` → versions/0001_init.py
2. Add `core/auth.py`:
   - password hashing (Werkzeug / argon2 later)
   - login endpoint (POST /auth/login) returning session cookie
   - decorator @require_roles(*roles)
3. Implement real `MenuService` (DB CRUD):
   - create_or_get_menu(tenant, week, year)
   - set_variant(...)
   - get_week_view(tenant, week, year, include_overrides=True)
4. Municipal endpoints:
   - GET /municipal/menu/week?week=&year=
   - POST /municipal/menu/variant (payload: week, year, day, meal, variant_type, dish_id)
5. Attendance endpoints (core):
   - PUT /attendance (set for date+meal)
   - GET /attendance/summary?week=&year=
6. Dietary endpoints:
   - GET /diet/assignments?unit=
   - POST /diet/assignments (unit, diet_type_id, count)
7. Import adapter skeleton: `core/importers/word_menu.py` (placeholder parse())
8. Export adapter skeleton: `core/exporters/daily_docx.py`
9. Turnus scheduling port (phase A): simple 6-cook generator from rotation_simple → SchedulingService impl
10. Turnus scheduling port (phase B): template + motor pattern / virtual mapping
11. Waste metrics endpoints (/offshore/metrics/log, /offshore/metrics/recommendation)
12. Reporting service: diet distribution + menu coverage
13. Implement tenant feature flag persistence table + loader
14. Data migration script (scripts/migrate_from_legacy.py) referencing docs/migration_plan.md

## 6. Coding Conventions
- Use type hints consistently
- Avoid runtime ALTER TABLE; always use Alembic
- Keep module-specific logic out of core code paths
- Use `@require_roles` for protected endpoints once auth is live
- Normalize day names to canonical: Mån, Tis, Ons, Tors, Fre, Lör, Sön (store lowercase English alias later if needed)

## 7. Edge Cases to Preserve
- Night shifts crossing midnight (end_ts < start_ts → add 1 day)
- Duplicate shift slot suppression in simple generator
- Attendance inheritance (previous week fallback) – implement later in AttendanceService
- Portion recommendation blending (sample-size weighted)
- Private/global override precedence

## 8. Migration Key Mappings (Planned)
- municipal.veckomeny → menus + variants
- municipal.kosttyper → dietary_types
- municipal.avdelning_kosttyp → unit_diet_assignments
- municipal.boende_antal → attendance
- offshore.turnus_slots → shift_slots
- offshore.service_metrics → service_metrics
- offshore.normative_portion_guidelines → portion_guidelines

## 9. Deployment Targets
- Development: SQLite + DEV_CREATE_ALL
- Production: PostgreSQL + Alembic migrations

## 10. Open Questions (Track in backlog)
- Year handling for historical municipal weeks
- Messaging attachments required? (not yet)
- SSO timeline

## 11. Ready-Made Health Check
GET /health returns modules + features list.

## 12. DO NOT (Anti-Goals)
- Duplicate old procedural logic; always refactor into a service
- Embed business logic directly in blueprints (keep thin controllers)
- Write migrations by hand without revision tracking

---
This file should be updated as milestones are completed. Add new sections rather than rewriting historical context to preserve reasoning trail.
