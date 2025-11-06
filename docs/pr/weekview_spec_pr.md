# design(weekview): spec, openapi draft, static mock (no logic)

Scope
- Design only: no DB, no routes, no JS logic.
- Establish contracts and UI skeleton for Weekview Module 1.

Included
- docs/weekview.md: goals, data model (draft), endpoints, RBAC, ETag/If-Match, ff.weekview.enabled, i18n keys.
- openapi/parts/weekview.yml: GET /api/weekview, PATCH /api/weekview (If-Match), POST /api/weekview/resolve (draft).
- ui/prototypes/weekview_mock.html: static layout (department × day × meal grid), no logic.
- tests/design/test_weekview_spec.py: placeholder checks for presence and key markers.

Definition of Done
- Spec + mock committed.
- i18n keys enumerated.
- ETag/If-Match and RBAC documented.
- CI/lint pass (placeholder tests green).

Notes
- Viewer policy for Weekview in M1: read-only vs 403 TBD; documented fallback (403) for consistency.
- Resolve endpoint is optional helper; may move to a separate module or be deferred to M2.
