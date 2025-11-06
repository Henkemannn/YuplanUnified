# design(weekview): spec, openapi draft, static mock (no logic)

Scope
- Design only: no DB, no routes, no JS logic.
- Establish contracts and UI skeleton for Weekview Module 1.

Included
- docs/weekview.md: goals, data model (draft), endpoints, RBAC, ETag/If-Match, ff.weekview.enabled, i18n keys, telemetry plan.
- openapi/parts/weekview.yml: GET /api/weekview, PATCH /api/weekview (If-Match), GET /api/weekview/resolve (idempotent helper).
- ui/prototypes/weekview_mock.html: static layout (department × day × meal grid) with Alt2 corner tag and marked-count ring; data-* attributes included (data-week, data-year, data-department-id, data-day, data-meal, data-diet, data-marked).
- tests/design/test_weekview_spec.py: placeholder checks for presence and key markers (RBAC matrix text, ETag/If-Match examples, GET resolve, i18n keys, data-* markers).

Definition of Done
- Spec + mock committed.
- i18n keys enumerated.
- ETag/If-Match and RBAC documented.
- CI/lint pass (placeholder tests green).

Notes
- Viewer policy finalized for M1: viewer can read (GET endpoints), cannot write (PATCH → 403).
- Resolve endpoint is an idempotent GET helper; may be deferred or relocated in later modules if needed.

Sign-off checklist
- [x] OpenAPI uses GET /api/weekview/resolve with query params.
- [x] ETag/If-Match documented with concrete header examples.
- [x] RBAC matrix: viewer can read (GET), cannot write (PATCH).
- [x] Week is represented as {year, week} across spec + mock.
- [x] UI mock shows Alt2 tag and green ring for marked counts.
- [x] i18n keys enumerated; no hardcoded strings in spec/mock.
- [x] Tests assert presence of the above markers.
- [x] Feature flag noted: ff.weekview.enabled.
