Planera Phase P1.2 — Week CSV Export + Print-Friendly Views

This PR adds export and print capabilities to the Planera module’s week view, building on the existing P1.1 aggregation. No new business logic is introduced; all numbers still come from the existing Planera/Weekview aggregation.

Scope

- Reuse existing Planera week aggregation for export.
- Add a CSV export endpoint for /api/planera/week.
- Add print-friendly styles and a simple print trigger for:
  - /ui/planera/week
  - /ui/planera/day
- Keep the module fully read-only.

API — /api/planera/week/csv

New endpoint: GET /api/planera/week/csv

Params: site_id, year, week, optional department_id (same as JSON week API).

Validates params and respects ff.planera.enabled.

Response:

- Content-Type: text/csv; charset=utf-8
- Header row: date,weekday,meal,department,residents_total,normal,special_diets
- One row per (day × meal × department).
- special_diets column contains semicolon-separated DietName:Count pairs, e.g. Gluten:2;Laktos:1.

ETag behavior:

- Shares the same logical ETag basis as the JSON week API (Planera aggregation).
- Supports If-None-Match:
  - Returns 304 Not Modified when the ETag matches.
  - Otherwise returns 200 with CSV body.

UI — Week View Export + Print

Week UI (/ui/planera/week):

- Adds an “Exportera CSV” button/link that:
  - Preserves current site/year/week/department_id in the CSV URL.
  - Points directly to /api/planera/week/csv?....

Day & Week Print Layout:

- New print stylesheet: static/css/planera_print.css.
- Linked from planera_day.html and planera_week.html with media="print".
- Print rules:
  - Hide non-essential UI (navigation/buttons) in print.
  - A4 portrait-friendly, condensed table styling.
  - Avoid horizontal scrolling for normal data sets.

Simple print trigger:

- “Skriv ut” button calling window.print() in both day and week templates.

Tests

New test coverage:

- test_planera_week_csv_export.py:
  - Verifies:
    - 200 OK for CSV export with flag enabled.
    - Content-Type is text/csv.
    - Header row is present.
    - At least one data row contains special_diets content.
  - Verifies conditional GET:
    - Second request with If-None-Match returns 304.

- UI checks:
  - Assert presence of:
    - “Exportera CSV” control in week UI.
    - “Skriv ut” button and media="print" stylesheet link in day/week templates.

Full test suite: passed (including new Planera tests).

Non-goals / Notes

- No changes to Weekview or Report logic.
- No changes to core Planera aggregation or business rules.
- No mutations added; Planera remains read-only in P1.2.
- Department filter behavior for week UI remains as in P1.1/P1.1.1 (this PR only wires export + print).

---

Det är bara att:

- Skapa PR från feat/planera-phase-p1-2-export → master.
- Sätta labels: module:planera, phase:P1.2, type:feature, area:api, area:ui, ready-for-review.

När PR-numret är uppe kan vi fortsätta planeringen för nästa modul (t.ex. Admin eller Avdelningsportalen) när Planera-blocket är helt integrerat.
