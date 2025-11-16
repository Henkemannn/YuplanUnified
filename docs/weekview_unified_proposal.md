# Unified Weekview (Kommun) – Implementationsförslag

Mål: Leverera en veckovy i Unified som är minst lika bra som legacy Yuplan (kommun), optimerad för iPad och användare utan datorvana. Läs‑först (Fas 1), därefter mutationer (Fas 2) med ETag/CSRF.

## Sammanfattning
- UI: Tabell med 7 dagar × (Lunch/Kväll) kolumner. Rader: Boende + en rad per kosttyp.
- Navigation: Vecka fram/bak + väljare. Avdelningsväljare. Utskrift.
- Tydlighet: Gulmarkering för Alt2 på lunch. Meny‑popup på dagshuvuden (Alt1/Alt2/Dessert/Kväll).
- Data: `GET /api/weekview` (marks, residents_counts, alt2_days, ETag); komplettera med menytexter.
- Fas 1: Read‑only UI + meny‑popup. Fas 2: PATCH för togglas/belopp samt Alt2 via If‑Match.

För exakt JSON‑schema, se [Weekview API schema](weekview_api_schema.md).

## UX/Design (iPad‑först)
- Layout
  - Sticky kolumnrubriker (dagar). Horisontell scroll inom tabellen vid mindre skärmar.
  - Första kolumn max 140–160 px (avdelningsnamn/kosttyp). Övriga celler centrerade.
  - Tydliga klickytor: dagshuvud öppnar meny‑popup. (Ingen cell‑toggling i Fas 1.)
- Element per dag
  - Huvud: "Mån … Sön" med liten ikon 📋 när meny finns.
  - Lunch/Kväll ikonrad (🍽️/🌙). Boende‑rad med antal per dag/måltid.
  - Kosttypsrader med förvalda siffror (read‑only i Fas 1).
- Visuella markeringar
  - Alt2‑dagar: gul bakgrund i lunchkolumner. Konsekvent med legacy.
  - Fokus och tangentnavigering (tab bar) för tillgänglighet.
- Responsivitet
  - iPad (1024×768) som primärmål. På smalare lägen visa horisontell scroll. På extremt smalt: alternativ kortvy (KAN v2).
- Utskrift
  - Print‑css som döljer kontroller och ger ren tabell.

## Rutter och URL‑modell
- UI‑rutt: `/ui/weekview?department_id=<uuid>&year=YYYY&week=WW`
  - Tenant tas från session.
  - Feature flagg: `ff.weekview.enabled` (redan stöd i backend) styr exponering.
- Dataanrop
  - `GET /api/weekview?department_id=<uuid>&year=YYYY&week=WW` med `If-None-Match` → 200/304 + `ETag`.
  - Menydata: utöka payload (se nedan) eller ny endpoint.

## Site-översikt & Meal Labels (Phase 1.1)
För site-översikt (en site, en vecka, alla avdelningar) se designen i: [Weekview Site Overview – Design](weekview_overview_design.md).

Måltidsnamn i UI hämtas via `meal_labels` (Phase 1.1). Backend behåller neutrala fält `lunch`/`dinner`. Se dokumentation i [Meal Labels](meal_labels.md). Default label för `dinner` är "Kvällsmat" tills per‑site konfiguration införs (framtida steg Offshore → "Middag").

## API‑kontrakt (förslag)
- Nuvarande svar från `GET /api/weekview` innehåller:
  - `department_summaries[0]`: `{ marks: [...], residents_counts: [...], alt2_days: [...] }`
- Föreslagen utökning (Fas 1):
  - Lägg till `menu_texts` per dag (mon..sun) och fält (alt1, alt2, dessert, kvall):
    ```json
    {
      "year": 2025,
      "week": 3,
      "department_summaries": [
        {
          "department_id": "<uuid>",
          "alt2_days": [1,3,5],
          "residents_counts": [...],
          "marks": [...],
          "menu_texts": {
            "mon": {"alt1": "…", "alt2": "…", "dessert": "…", "kvall": "…"},
            "tue": { ... }
          }
        }
      ]
    }
    ```
  - Alternativ (om vi vill separera): `GET /api/menu?department_id=<uuid>&year=YYYY&week=WW` med samma struktur. Rekommendation: bädda in i weekview för enkel klient och färre rundresor.

## Fasplan
- Fas 1 – Read‑only (MÅSTE för parity)
  - UI: Tabellvy, gulmarkering för Alt2, boende‑rad, kosttypsrader (read‑only), meny‑popup via `menu_texts`.
  - Data: `GET /api/weekview` + `If-None-Match`. Payload utökas med `menu_texts`.
  - Navigation: vecka fram/bak, väljare, avdelningsval (dropdown eller parameter).
  - Utskrift: enkel CSS för ren PDF.
- Fas 2 – Mutationer (KAN för parity, men önskvärd)
  - PATCH `/api/weekview` – toggla markeringar per dag/måltid/kosttyp. If‑Match via `ETag` från GET.
  - PATCH `/api/weekview/residents` – uppdatera boendeantal per dag/måltid (batch). If‑Match.
  - PATCH `/api/weekview/alt2` – sätt Alt2‑dagar (1..7). If‑Match.
  - CSRF: befintlig cookie/header.

## Datakopplingar
- Legacy → Unified (redan tillgängligt eller delvis):
  - Markeringar → `weekview_registrations` (repo) / `PATCH /api/weekview`.
  - Boendeantal → `weekview_residents_count` / `PATCH /api/weekview/residents`.
  - Alt2‑dagar → `weekview_alt2_flags` / `PATCH /api/weekview/alt2`.
  - Veckomeny → `Menu` + `MenuVariant` – mappa in i `menu_texts` (servern kan rendera text från dish/recipe, fallback ren text som i legacy `veckomeny`).

## Tekniska beslut
- Caching: `If-None-Match`/`ETag` för GET. `Cache-Control: private, max-age=0, must-revalidate`.
- Felhantering: ProblemDetails (ADR‑003). UI visar vänliga meddelanden + retry.
- Tillgänglighet: semantiska tabeller, fokusmarkeringar, ARIA för popup.
- Feature flag: `ff.weekview.enabled` måste vara aktiverad per tenant.
- Rollskydd: `viewer` får läsa; `admin/editor` får mutera i Fas 2.

## Acceptanskriterier (Fas 1)
- Visa vald avdelning och vecka i tabell: 7 dagar × (Lunch/Kväll), rader: Boende + kosttyper.
- Alt2‑dagar syns tydligt (gul lunchkolumn) och matchar `alt2_days`.
- Boendeantal per dag/måltid visas.
- Meny‑popup på dagshuvud visar Alt1, Alt2, Dessert, Kväll.
- Navigera vecka (fram/bak) och via väljare. Utskrift fungerar.
- Fungerar på iPad utan horisontell scroll i viewportbredd ≥1024px, annars smidig scroll.
- `GET /api/weekview` med `If-None-Match` ger 304 när inget ändrats.

## Acceptanskriterier (Fas 2)
- Markeringstoggle per cell skickar PATCH `/api/weekview` med If‑Match; 412 hanteras med uppdatering och retry.
- Uppdatering boendeantal via PATCH `/api/weekview/residents`.
- Sätta Alt2‑dagar via PATCH `/api/weekview/alt2`; helgdagar kan blockeras enligt policy (om menypolicyn kräver).
- CSRF och rollkrav efterlevs.

## Implementationssteg
1. Backend (Fas 1)
   - Utöka `WeekviewRepo.get_weekview` eller service‑lagret att inkludera `menu_texts` (mon..sun, alt1/alt2/dessert/kvall) – hämtat från `Menu`/`MenuVariant` eller en liten adapter mot legacy `veckomeny` om Unified‑data saknas.
   - Säkerställ `ff.weekview.enabled` default aktiverad för dev/staging.
2. UI (Fas 1)
   - Ny template/route: `/ui/weekview` (Flask, server‑render initial state + hydrering eller enkel fetch i JS).
   - Tabellmarkup + CSS (sticky headers, print‑css). Meny‑popup.
   - Navigationskomponent (vecka fram/bak, väljare, avdelningsdropdown).
3. Backend (Fas 2)
   - Säkerställ PATCH‑vägarna är stabila (de finns redan) + CSRF.
4. UI (Fas 2)
   - Cell‑toggle + boendeantal‑form (inline) + Alt2‑dagväljare med If‑Match och konflikthantering.

## Risker & Mitigering
- Menydata saknas i Unified: börja med fallback från legacy tabell eller tillsvidare tom‑state i popup.
- UUID/department‑mapping: verifiera att valda testdata finns för end‑to‑end.
- ETag‑konflikter i multiuser: implementera återläsning + tydlig toast.

## Prioritering
- MÅSTE (v1): Read‑only tabell, Alt2‑visning, meny‑popup, navigering, utskrift, iPad‑optimering.
- KAN (v2): Kortvy, snabbfilter, summeringar per dag, offlinecache, tangentgenvägar.
