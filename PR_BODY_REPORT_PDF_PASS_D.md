# Pass D – Rapport: Exportera PDF (klientside via print)

Det här lägger till “Export PDF” i Rapport-panelen. Funktionen bygger en print-vy från redan inläst rapportdata och använder webbläsarens `window.print()` för att skapa en PDF (via systemets skrivare/“Spara som PDF”). Ingen serverförändring krävs och CSP-respekteras.

Vad som ingår:
- UI: Ny knapp “Export PDF” bredvid “Läs in” och “Export CSV”.
- JS: `exportReportPdf(reportJson, week)` och `renderPrintReport(...)` för att generera tabell + summering.
- CSS: `@media print` för A4, 12mm marginaler; döljer header/meny/knappar i utskrift; enklare kortlayout.
- A11y/UX: Fokus återställs till knappen efter utskrift.
- Test: Minimal jsdom-enhetstest för print-vy byggaren.
- Docs: README-sektion “Rapport – Exportera PDF (Pass D)”.

Test/Verifiering:
1) Ladda Rapport (välj vecka, “Läs in”).
2) Klicka “Export PDF” → förhandsgranskning visar rubrik, tabell och totals. Svenska tecken renderas korrekt.
3) Avbryt/Skriv ut.

Risk/Scope:
- Klientside-only. Ingen backend- eller API-förändring. Print-vy är isolerad i ett temporärt DOM-element och städas bort.
