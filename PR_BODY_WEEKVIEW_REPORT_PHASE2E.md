# Weekview Report Phase 2.E – Design & Skeleton

## Scope
Design + skeleton only for a read-only weekly report that summarizes special diets and normal diets per meal (Lunch/Kvällsmat) per department. Uses existing Weekview outcome data; no new persistence.

## Deliverables in this PR
- `docs/weekview_report_phase2e.md`: Detailed design (scope, data sources, aggregation rules, API shape, UI layout, error handling, future extensions).
- Linked section added to `docs/weekview_unified_proposal.md` pointing to the new report doc.
- Skeleton API endpoint: `GET /api/reports/weekview` returning placeholder structure (all counts = 0, empty `special_diets`).
- Skeleton UI route: `/ui/reports/weekview` with header + "Coming soon" message + debug JSON dump.
- Basic test: `tests/reports/test_weekview_report_phase2e_skeleton.py` asserting API shape & UI status.

## API (Placeholder)
`GET /api/reports/weekview?site_id=...&year=YYYY&week=WW[&department_id=...]`
Returns:
```
{
  "site_id": "...",
  "site_name": "...",
  "year": 2025,
  "week": 12,
  "meal_labels": {"lunch": "Lunch", "dinner": "Kvällsmat"},
  "departments": [
    {
      "department_id": "...",
      "department_name": "Avd X",
      "meals": {
        "lunch": {"residents_total": 0, "special_diets": [], "normal_diet_count": 0},
        "dinner": {"residents_total": 0, "special_diets": [], "normal_diet_count": 0}
      }
    }
  ]
}
```
(Counts & lists are placeholder until Phase 2.E.1.)

## UI Skeleton
- Header: `Statistik – vecka {week} – {site_name}` (adds department name if single scope).
- Lists each department as an empty card with explanatory text.
- "Coming soon" message clarifies aggregation not yet implemented.

## Tests
- Verifies top-level keys & placeholder meal object structure.
- Ensures UI route returns 200 and contains the header and coming-soon message.

## Non-Goals (Explicit)
- No aggregation logic yet (normal diet or special diet summations).
- No mutations, exports, or localization enhancements.
- No caching beyond existing application behavior.

## Next Phase (2.E.1 Preview)
Will implement real aggregation, normal diet derivation, sorted special diets, warnings for missing data, and production UI cards.

---
Ready for review. Merging this establishes the contract and lets Phase 2.E.1 focus on logic & UX refinement.
