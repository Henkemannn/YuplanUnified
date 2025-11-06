# Weekview – Module 1 Design Spec (Draft)

## Goals
- Provide a weekly planning view to admins and editors with a department × day × meal grid.
- Enable quick navigation from Dashboard to Weekview.
- Establish contracts (API, RBAC, concurrency, flags, i18n) before implementation.

## Data model (draft)
- WeekView
  - week_start: date (ISO, Monday-based)
  - week_end: date (ISO)
  - department_summaries: [DepartmentSummary]
- DepartmentSummary
  - department_id: string
  - department_name: string
  - days: [DayPlan]
- DayPlan
  - date: date (ISO)
  - meals: [MealSlot]
- MealSlot
  - kind: enum [breakfast, lunch, dinner]
  - items: [Item]
- Item
  - id: string (ULID/UUID)
  - title: string
  - notes: string | null
  - status: enum [planned, confirmed, canceled]
  - assigned_to: string | null

Notes:
- This is a UI-facing shape; persistence model may differ.

## API Endpoints (draft)
- GET /api/weekview
  - Query: start=YYYY-MM-DD, end=YYYY-MM-DD, department=[id]? (optional)
  - Response: 200 application/json → WeekView
  - Caching: Cache-Control: no-store
- PATCH /api/weekview
  - Headers: If-Match: <etag> (required)
  - Body: RFC6902 JSON Patch or typed ops (TBD)
  - Responses: 200 on success (new representation + ETag), 400 invalid ops, 412 if ETag mismatch
- POST /api/weekview/resolve
  - Purpose: server-side conflict resolution helper (optional in M1)
  - Body: conflict payload (TBD)
  - Responses: 200 resolution result, 400 invalid payload

OpenAPI draft lives at openapi/parts/weekview.yml.

## RBAC
- Admin: read + write
- Editor: read + write
- Viewer: read-only (TBD if route accessible for viewer in M1; fallback to 403)
- CSRF: enforced for state-changing endpoints (PATCH, POST)

## Concurrency – ETag / If-Match
- GET returns ETag for the current week range and department slice.
- PATCH requires If-Match; backend returns 412 (RFC 9110) when ETag mismatch.
- 304 Not Modified allowed on conditional GETs; body MUST be empty on 304.
- Error shape: RFC7807 problem+json for 400/412 with actionable details.

## Feature flag
- ff.weekview.enabled
  - When false, UI route returns 404; API endpoints return 404 or 403 depending on exposure policy.
  - Default: disabled until sign-off; enable per-tenant via overrides.

## i18n keys (initial)
- weekview.title
- weekview.toolbar.today
- weekview.toolbar.prev
- weekview.toolbar.next
- weekview.filters.department
- weekview.grid.header.monday
- weekview.grid.header.tuesday
- weekview.grid.header.wednesday
- weekview.grid.header.thursday
- weekview.grid.header.friday
- weekview.grid.header.saturday
- weekview.grid.header.sunday
- weekview.meal.breakfast
- weekview.meal.lunch
- weekview.meal.dinner
- weekview.empty.no_items
- weekview.status.planned
- weekview.status.confirmed
- weekview.status.canceled

## Non-goals (M1)
- Complex filters, pagination, or exports.
- Background recomputation and caching.
- Full CRUD for items; M1 focuses on representation + minimal updates.

## Success criteria (DoD for this PR)
- Spec committed here aligns with OpenAPI draft and static mock.
- i18n keys enumerated.
- RBAC and ETag/If-Match behavior documented.
- CI/lint pass and placeholder tests green.
