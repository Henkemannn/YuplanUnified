# Weekly Report – PDF-export

Exports the weekly report as a print-friendly PDF.

- Route: `/ui/reports/weekly.pdf`
- Parameters: `site_id`, `year`, `week`

## Template and Layout
- Uses `templates/ui/unified_report_weekly_print.html` with an A4-friendly layout.
- Clear title: "Veckorapport – vecka {{ vm.week }}, {{ vm.year }}".
- Site information at the top.
- Simple table summarizing weekly coverage per department.
- Print-focused styling (no interactive elements).

## Data Source
- Uses the same coverage data as the HTML, CSV, and Excel weekly reports
  (`ReportService.get_weekly_registration_coverage`).

## Response Details
- MIME: `application/pdf`
- Filename: `veckorapport_v{week}_{year}.pdf`
- The PDF is returned as an attachment for download.
