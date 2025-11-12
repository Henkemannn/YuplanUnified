# Module 1 – Weekview: planning & scope

## Goals
- Deliver a Weekview page that surfaces upcoming work by week for admins and editors.
- Provide quick navigation from Dashboard quickstart to Weekview.
- Establish a minimal, testable slice that can be iterated (MVP → M1).

## Assumptions
- Auth and RBAC already exist (admin/editor allowed; viewer read-only or redirected).
- Feature flag model is available (e.g., ff.weekview.enabled if needed).
- Flask + blueprint architecture continues.

## In Scope (M1)
- New UI route: GET /weekview (Blueprint: ui or weekview).
- Server-side: basic template render, no heavy data aggregation yet.
- Minimal topbar + layout; match Dashboard styling where reasonable.
- Placeholder “This week” section with stub data or empty state.
- RBAC: admin/editor allowed; viewer behavior to be defined (likely read-only or 403 consistent with dashboard policy).
- Feature flag (optional): ff.weekview.enabled → 404 if off.
- Tests: route availability, RBAC, FF-off 404, minimal structure assertions.
- Link integration: Ensure /dashboard quickstart link to /weekview remains green.

## Out of Scope (M1)
- Advanced filters (department, assignee, tags).
- Cross-tenant overrides beyond usual FF mechanism.
- Performance optimization and caching.
- Full data model changes or migrations.

## Deliverables
- Blueprint and template(s) for Weekview.
- Minimal CSS additions (reuse dashboard.css where possible).
- pytest coverage for auth/FF/structure.
- Docs update in docs/modules.md and docs/roadmap.md.

## Dependencies
- Existing auth/session and has_role context helper.
- Feature flag scaffolding.
- CI tests running for new routes and templates.

## Risks / Questions
- Viewer policy consistency: allow read-only vs 403 for Weekview?
- Data source readiness: if not ready, commit to clear empty-state text and test fixtures.
- Label taxonomy for tracking (dashboard vs weekview labels).

## Acceptance Criteria
- Visiting /weekview as admin/editor returns 200 with basic layout elements present.
- Visiting /weekview as viewer respects chosen policy (documented and tested).
- With ff.weekview.enabled = False, /weekview returns 404 in tests.
- Dashboard quickstart link to /weekview is visible for admin/editor and disabled for viewer, matching dashboard rules.
- Cache-Control: no-store applied to /weekview responses.

## Timeline (proposal)
- Day 1–2: Scaffold blueprint, template, tests (red→green).
- Day 3: Wire FF and RBAC, align styles; add docs.
- Day 4: PR review, squash-merge, tag minor version.

## Definition of Done
- All tests pass locally and in CI; coverage for new code paths.
- PR merged with labels and changelog entry; feature flag defaults documented.
- No-store headers verified for /weekview; links from dashboard validated.
