# Weekview – Module 1 Design Spec (Draft)

## Goals
- Provide a weekly planning view to admins and editors with a department × day × meal grid.
- Enable quick navigation from Dashboard to Weekview.
- Establish contracts (API, RBAC, concurrency, flags, i18n) before implementation.

## Data model (draft)
- WeekView
  - year: int (ISO year)
  - week: int (ISO week number 1..53)
  - week_start: date (ISO, Monday-based)
  - week_end: date (ISO)
  - department_summaries: [DepartmentSummary]
- DepartmentSummary
  - department_id: string (UUID)
  - department_name: string
  - department_notes: [string] (display-only)
  - days: [DayPlan]
- DayPlan
  - date: date (ISO)
  - day_of_week: int (ISO: Mon=1..Sun=7)
  - meals: [MealSlot]
- MealSlot
  - kind: enum [lunch, dinner]
  - items: [Item]
- Item
  - id: string (ULID/UUID)
  - title: string
  - notes: string | null
  - diet_type: string (extensible; examples: normal, gluten_free, lactose_free, vegetarian, texture_timbal)
  - status: enum [planned, confirmed, canceled]
  - assigned_to: string | null

Notes:
- This is a UI-facing shape; persistence model may differ.

## API Endpoints (draft)
- GET /api/weekview
  - Query: year={int}, week={1..53}, department_id={uuid}? (optional)
  - Response: 200 application/json → WeekView
  - Headers: ETag: "W/\"weekview:dept:{uuid}:week:{int}:v{n+1}\""
  - Caching: Cache-Control: no-store
- PATCH /api/weekview
  - Headers: If-Match: "W/\"weekview:dept:{uuid}:week:{int}:v{n}\"" (required)
  - Body: RFC6902 JSON Patch or typed ops (TBD)
  - Responses: 200 on success (new representation + ETag), 400 invalid ops, 412 Precondition Failed on ETag mismatch with problem.type = "etag_mismatch"
- GET /api/weekview/resolve
  - Query: site={id}, department_id={uuid}, date={YYYY-MM-DD}
  - Responses: 200 OK with payload, 404 if not resolvable, standard ProblemDetails on errors

OpenAPI draft lives at openapi/parts/weekview.yml.

## RBAC
RBAC matrix (when ff.weekview.enabled is ON):
- GET /api/weekview → admin, staff, viewer = 200 (read)
- GET /api/weekview/resolve → admin, staff, viewer = 200 (read)
- PATCH /api/weekview → admin, staff = 200 (write); viewer = 403

Notes:
- CSRF enforced for state-changing endpoints (PATCH).

## Concurrency – ETag / If-Match
- GET returns ETag for the current week and department slice.
- PATCH requires If-Match; backend returns 412 (RFC 9110) when ETag mismatch.
- 304 Not Modified allowed on conditional GETs; body MUST be empty on 304.
- Error shape: RFC7807 problem+json for 400/412 with actionable details.

Header examples:
- Request: If-Match: "W/\"weekview:dept:{uuid}:week:{int}:v{n}\""
- Response: ETag: "W/\"weekview:dept:{uuid}:week:{int}:v{n+1}\""

## Feature flag
- ff.weekview.enabled
  - When false, UI route returns 404; API endpoints return 404 or 403 depending on exposure policy.
  - Default: disabled until sign-off; enable per-tenant via overrides.
  - RBAC matrix above applies only when this flag is enabled.

## i18n keys (complete list for M1)
- weekview.title
- weekview.weekSelector.label
- weekview.department.label
- weekview.meal.lunch
- weekview.meal.dinner
- weekview.alt2.label
- weekview.cell.marked
- weekview.cell.unmarked
- weekview.tooltip.noPermission
- weekview.error.etagMismatch
- weekview.error.generic

## Telemetry (spec only)
- Events: weekview_load, weekview_cell_toggled
- Dimensions: tenant_id, site_id, department_id, year, week, meal, diet_type, source=ui/api

## Non-goals (M1)
- Complex filters, pagination, or exports.
- Background recomputation and caching.
- Full CRUD for items; M1 focuses on representation + minimal updates.

## Success criteria (DoD for this PR)
- Spec committed here aligns with OpenAPI draft and static mock.
- i18n keys enumerated.
- RBAC and ETag/If-Match behavior documented.
- CI/lint pass and placeholder tests green.

Week representation carries {year, week} across spec and mock.
