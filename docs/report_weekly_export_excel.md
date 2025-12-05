# Weekly Report – Excel-export (XLSX)

This endpoint exports the weekly report as an `.xlsx` file suitable for Microsoft Excel.

- Route: `/ui/reports/weekly.xlsx`
- Parameters:
  - `site_id`
  - `year`
  - `week`

## Content
- One sheet named e.g. "Veckorapport".
- Header row (similar to CSV):
  - `Site`, `Avdelning`, `År`, `Vecka`, `Måltid`, `Boende totalt`, `Specialkost`, `Normalkost`.
  - Optional: date/weekday columns may be added in future phases if needed.
- One row per `avdelning × måltid` (department × meal) with weekly totals.

## Notes
- The data mirrors the HTML weekly report and the CSV export.
- The file is returned with MIME `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` and a filename like `veckorapport_v{week}_{year}.xlsx`.
