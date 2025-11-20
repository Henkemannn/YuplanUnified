Planera – Phase P1 Skeleton (API + UI + Tests)

This PR introduces the foundational skeleton for the Planera module (Phase P1) as defined in
`docs/planera_module_functional_spec.md`.

No real aggregation or business logic is implemented yet.
The goal of this PR is to establish stable contracts, routes, templates, and test scaffolding to enable Phase 1.1 aggregation to drop in cleanly.

API

Two new read-only endpoints:

GET /api/planera/day

Params: site_id, date (YYYY-MM-DD), optional department_id

Validates params and site/department existence

Returns correct Planera P1 schema with placeholder data:

departments[]

meals.lunch / meals.dinner

totals per meal

meal_labels

Supports:

ETag header

If-None-Match → 304

GET /api/planera/week

Params: site_id, year, week, optional department_id

Returns weekly Planera schema with:

days[] (date + weekday)

meals for lunch/dinner per day

weekly_totals

Both endpoints match the structure defined in the spec document.

UI

Two new screens in the UI blueprint:

GET /ui/planera/day

Renders header + site/date

Table structure for lunch/dinner:

Avdelningar

Boende

Specialkost

Normalkost

Uses API response as-is (dummy data for now)

GET /ui/planera/week

Weekly overview page

Renders day rows × meals with correct table structure

Feature flag gate (ff.planera.enabled) is deferred for skeleton, but left as TODO for Phase P1.1.

Tests

Added:

test_planera_day_skeleton.py

test_planera_week_skeleton.py

Both verify:

Endpoints return correct top-level keys

UI renders with 200 and expected headers

Placeholder structures match canonical schema

Full suite after this PR:
365 passed, 7 skipped

Non-functional

Added docs/planera_module_functional_spec.md with full P1 design

Zero changes to Weekview or Report modules

Safe for merge prior to implementing real aggregation

Next steps (Phase P1.1)

After this PR:

Add ff.planera.enabled feature gating

Implement real aggregation using Weekview service:

residents

special diets (marked only)

normal = residents - special

per-avdelning and kitchen totals

Add CSV export and print stylesheet

Extend tests to verify real numbers

📌 Done.

This PR sets the foundation for the full Planera module.

Closes #ISSUE_PLACEHOLDER