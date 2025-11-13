# Pass B – Menyval (Alt 1/Alt 2)

## Summary
Implementerar Menyval-panelen enligt kontraktet: vardagar Alt 1/Alt 2, helg endast Alt 1 (422 på försök). Hash-alias #alt2 → #menyval. ETag-medveten klient (If-None-Match/If-Match), optimistisk uppdatering med robust 204/412/422-hantering. Weekview-highlight i bärnsten för Alt 2. A11y (aria-pressed, Enter/Space) och debounce.

## Changes
- UI: Ny panel Menyval (#panel-menyval) med segmenterade dagkontroller (mån–sön).
- Routing: Alias #alt2 → #menyval; sidomeny uppdaterad till “Menyval”.
- API-klient:
  - GET /menu-choice med If-None-Match → 304 hanterad.
  - PUT /menu-choice kräver If-Match + CSRF → 204 uppdaterar ETag, 412 re-GET + banner, 422 helgregel-feedback.
- UX/A11y:
  - Tooltips (SV): “Visar alternativt menyval för dagen.”, “Alt 2 är endast tillåtet måndag–fredag.”, “Alt 1 är standardvalet.”
  - aria-pressed, Enter/Space support, klick-debounce (300 ms).
  - Statusbanner (auto-hide 2s) för 204/412/422.
- Weekview: .alt2-active i bärnsten (diskret bakgrund + outline).
- CSP/CSRF: Ingen inline-JS/CSS; PUT skickar CSRF-header/cookie.

## Testing
- Unit (API): ETag-idempotens, 304, 412, 422 (helg) → PASS.
- UI manuellt: toggles vardag; helg disabled + tooltip; weekview highlight synkad; stale (412) → auto refresh.

## How to verify (manual)
- Logga in som admin (cookies/CSRF), ladda departments, välj vecka + avdelning.
- #menyval: toggla t.ex. tisdag Alt1↔Alt2 → ETag uppdateras, statusbanner visas.
- #veckovy: se bärnstens-highlight på dagar med Alt 2.
- Försök Alt 2 på lördag → 422 + banner.
- Ladda om: If-None-Match ger 304 när orört.

## Security
- Strikt CSP (ingen inline).
- CSRF på skrivningar.
- Inga nya externa källor.

## Backward compatibility
- #alt2 aliasas till #menyval.
- Ingen ändring av statistik/rapport (Menyval är visuellt stöd).

## Checklist
- UI/ETag/Helgregel enligt brief
- Tests PASS
- Staging-kontroll OK
- Inga rapportpåverkande förändringar
