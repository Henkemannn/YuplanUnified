# Pass C – Rapport: Exportera CSV (klientside, CSP-säkert)

## Summary
Lägger till “Exportera CSV” i Rapport-panelen. Allt sker klientside från redan inläst rapportdata. CSV öppnas korrekt i Excel (UTF-8 BOM, semikolon, CRLF). Ingen serverändring.

## Changes
- UI: Knapp “Exportera CSV” bredvid “Läs in”, med aria-label och disabled state tills data finns.
- JS:
  - Serializer `toCsv(report, { week, departmentName })`: BOM + `;` + CRLF, korrekt quoting för specialtecken (ÅÄÖ, semikolon, radbrytning, ").
  - Filnamn: `report_v{week}_{departmentSlug}_{YYYYMMDD-HHmm}.csv` (Europe/Stockholm).
  - `downloadBlob(...)` för nedladdning (Blob + object URL + revoke).
  - Wiring: enable/disable baserat på om rapportdata är laddad.
- CSS: Fokusring och disabled-stil i linje med nuvarande knappar.
- Tests: Enhetstest för serializer (BOM, semikolon, CRLF, quoting) via vitest.
- Docs: README-sektion “Rapport – Exportera CSV (Pass C)”.

## Testing
- Python tests: PASS (pytest).
- Frontend tests: PASS (vitest för serializer).
- Manuell: Ladda Rapport, klicka “Exportera CSV” → öppna i Excel → rubriker och värden stämmer, svenska tecken OK.

## Security / CSP
- Ingen inline-JS/CSS. Befintlig CSP bibehållen.
- Ingen ny endpoint eller serverlogik. ETag-flöden oförändrade.

## Checklist
- Knapp syns och är aktiverad när data finns
- Serializer uppfyller BOM/“;”/CRLF/quoting
- Tests PASS
- Docs uppdaterade
