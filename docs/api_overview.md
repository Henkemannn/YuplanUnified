# API Overview

Base URL: (depends on deployment) all endpoints are JSON unless file upload.
Authentication: Session cookie after POST /auth/login
Content-Type: application/json for request bodies unless noted.

## Auth
POST /auth/login {email,password}
POST /auth/logout
GET /auth/me -> {user_id, role, tenant_id, unit_id}
Rate limiting: see docs/auth_hardening.md

## Admin & Tenants
GET /admin/tenants
POST /admin/tenants {name}
POST /admin/feature/toggle {tenant_id, name, enabled}

## Menu
GET /menu/week?week=40&year=2025 -> {menu_id, days{ day{ meal{ variant_type{ dish_id, dish_name }}}}}
POST /menu/variant/set {week,year,day,meal,variant_type,dish_id?|dish_name?}

## Import
POST /import/menu (multipart file=form field "file")
Query: dry_run=1 returns {dry_run:true, diff:[{week,year,day,meal,variant_type,dish_name,dish_new,variant_action}]}
Otherwise returns summary weeks array: {weeks:[{week,year,created,updated,skipped,total}], warnings, errors}

## Turnus (Scheduling)
GET /turnus/templates
POST /turnus/templates {name, pattern_type}
POST /turnus/import {template_id, shifts:[{unit_id,start_ts,end_ts,role}]}
GET /turnus/slots?from=YYYY-MM-DD&to=YYYY-MM-DD&unit_ids=1,2&role=cook

## Diets & Attendance
POST /diet/type {name, default_select}
GET /diet/types
DELETE /diet/type/<id>
POST /diet/assign {unit_id,dietary_type_id,count}
GET /diet/assign?unit_id=1
DELETE /diet/assign/<id>
PUT /attendance {unit_id,date,meal,count}
GET /attendance/summary?from=YYYY-MM-DD&to=YYYY-MM-DD

## Service Metrics
POST /metrics/service {unit_id,date,meal,dish_id?,category?,guest_count?,produced_qty_kg?,served_qty_kg?,leftover_qty_kg?}
GET /metrics/service/query?from=YYYY-MM-DD&to=YYYY-MM-DD&unit_id=1
GET /metrics/service/day?date=YYYY-MM-DD&unit_id=1
GET /metrics/service/summary?from=YYYY-MM-DD&to=YYYY-MM-DD&unit_id=1

## Feature Flags
GET /admin/tenants includes feature flags & metadata
(Manipulation via POST /admin/feature/toggle)

## Health
GET /health -> {ok, modules, features}

## Notes
- Multi-tenancy enforced by session tenant_id.
- Roles: superuser | admin | cook | unit_portal (some read-only access).
- Future endpoints (not yet implemented): OpenAPI spec, menu overrides, advanced turnus templates, messaging.
