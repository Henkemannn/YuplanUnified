# Unified Portal – Avdelningsvy (Veckovy)

En enkel, läsbar avdelningsvy för omsorgs-/avdelningspersonal och kök. Sidan visar veckans måltider per dag med tydliga kort och badges.

## Syfte
- Avdelningsnivå veckovy (7 dag-kort) för lunch/kväll.
- Snabb överblick: huvudrätt (alt1), alternativ (alt2), dessert, diet-badges och registreringsstatus.

## Teknisk not
- Återanvänder befintlig portal-route och `vm` (ingen ny backend eller API).
- Renderar `templates/unified_portal_week.html` via `/portal/week` med oförändrad payload.

## Innehåll
- 7 dag-kort med datum och veckodag.
- LUNCH-block (alltid när meny finns) och KVÄLLSMAT-block (när vecka innehåller middag).
- Badges:
  - ⚡ Alt 2 (när vald)
  - Dieter: t.ex. `Gluten [2]`, `Laktos [1]`
  - Registrering: `Registrerad` / `Ej gjord`

## Tillgänglighet
- Varje måltidsblock är ett interaktivt element:
  - `role="button"`, `tabindex="0"`
  - Beskrivande `aria-label` (innehåller: veckodag, datum, registreringsstatus, alt2, diet-summering).
- Tangentbord:
  - `T` scrollar till dagens kort (om markerat).
  - `Enter`/`Space` på ett fokuserat måltidsblock triggar samma händelse som klick.

## Skärmdumpar

![Portal week desktop](screenshots/portal_week_desktop.png)

![Portal week narrow](screenshots/portal_week_narrow.png)

> Lägg till PNG:er i `docs/screenshots/portal_week_desktop.png` och `docs/screenshots/portal_week_narrow.png` (manuellt från lokal körning).

## Läs mer
Se `README.md` — Unified design tokens och övergripande utvecklingsflöde.
