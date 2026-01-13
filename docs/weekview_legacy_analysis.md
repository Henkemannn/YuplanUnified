# Weekview (Legacy Kommun) – Analys och Unified-förslag

Detta dokument sammanfattar hur legacy‑veckovyn (kommun) är uppbyggd – utseende, funktion och dataflöde – samt ett förslag på hur den bör byggas i Unified.

## Hittade källor (legacy)

- Templates (HTML)
  - `legacy/kommun/templates/veckovy.html` (personal/kockvy för vecka)
  - `legacy/Yuplan3.5/templates/veckovy.html` (senaste kopian; samma struktur med control‑bar, tabell, meny‑popup)
  - Relaterade vyer/länkar i topp: `planera.html`, `rapport.html`, `redigera_boende.html`, `adminpanel.html`
- JavaScript (interaktion)
  - `legacy/kommun/static/script.js` och `legacy/Yuplan3.5/static/script.js` (klick på celler, gulmarkering av lunch, POST → `/registrera_klick`)
  - Inlinescript i `veckovy.html` (Meny‑popup, klick på veckodagsrubriker)
- Controllers/Routes (Flask)
  - `legacy/kommun/app.py` och `legacy/Yuplan3.5/app.py`
    - `@app.route("/veckovy") def veckovy()` – renderar `veckovy.html`
    - `@app.route("/registrera_klick", methods=["POST"])` – sparar cellklick/markering
    - `@app.route("/planera/<int:vecka>")` – planeringsflöden (Alt1/Alt2, kosttyper)
    - `@app.route("/rapport")` – rapport/aggregat
    - `@app.route("/redigera_boende/<int:avdelning_id>")` – boendeantal per dag/måltid

Datakällor i legacy (SQLite‑tabeller lästa i `veckovy()` – bekräftat i `legacy/Yuplan3.5/app.py`):
- `avdelningar`, `kosttyper`, `avdelning_kosttyp` (koppling + antal per kosttyp)
- `registreringar` (markeringar per dag/måltid/kosttyp)
- `boende_antal` (override av boende per dag/måltid och vecka)
- `alt2_markering` (dagar där Alt2 valts – gulmarkering lunch)
- `veckomeny` (menytexter per dag/alt)

---

## Utseende i legacy‑veckovy

- Layout
  - Tabellbaserad vy per avdelning: 7 dagar som kolumner, varje dag har 2 kolumner (Lunch, Kväll)
  - Första kolumnen: radrubriker (avdelningsnamn, "Boende", därefter en rad per kosttyp)
  - Överst en kontrollrad ("control‑bar") med vecka‑väljare och actions
- Element per dag
  - Veckodag (Mån…Sön) som header‑celler, markerade med klass `veckodag-header`
  - Ikoner i andraraden: 🍽️ för Lunch (klass `dagstart`), 🌙 för Kväll (klass `kväll`)
  - Rad "Boende": antal boende per dag/måltid (hämtat från `boende_antal` alt. fallback)
  - Rad per kosttyp: antal (från koppling), celler klickbara för markering (klass `kostcell`)
- Visuella markeringar
  - Markering av specialkostcell: klass `markerad` (fetstil + cirkelram via `::before`)
  - Alt2‑val på lunch: klass `gulmarkerad` (gul bakgrund) på lunchceller den dagen
  - Kvällsrader har grön ton (`.kväll { background-color: #e0ffe0; }`)
  - Dagens datum/helgdagar: ingen explicit logik, men helger (Lör/Sön) finns visuellt som kolumner
- Popup “Meny”
  - Klick på veckodagsrubrik öppnar en meny‑popup med Alt1, Alt2, Dessert, Kväll (hämtas ur `meny_data`)
- Responsivitet
  - Primärt tabell: första kolumn maxbredd 140px; övriga centrerade
  - Ingen tydlig mobilbrytpunkt i CSS; på iPad förväntas tabell med horisontell scroll
  - Utskriftläge: egna regler (döljer kontroller, ren tabell för print)

---

## Funktioner i legacy‑veckovy

- Navigation
  - Vecka: select (1–52/53) + "Byt" knapp i formulär som GET mot `/veckovy?vecka=X`
  - Länkar till "Planera måltider" (`/planera/<vecka>`) och "Statistik" (`/rapport`)
  - Avdelningsbyte: i denna vy renderas alla avdelningar under varandra; filtrering finns i rapporter/planera
- Interaktion
  - Klick på kostcellsdata (`td[data-*]`) togglar `markerad` och skickar POST till `/registrera_klick` med { vecka, dag, måltid, avdelning_id, kosttyp_id, markerad }
  - Klick på veckodagsrubrik
    - Gulmarkerar lunchceller i tabellen för den dagen (JS i `static/script.js`)
    - Öppnar meny‑popup (inline JS i `veckovy.html`)
  - Utskrivbar – knapp i kontrollfältet kör `window.print()`
- Kopplingar
  - Veckomeny (`veckomeny` tabell) → popup med Alt1/Alt2/Dessert/Kväll
  - Alt1/Alt2
    - Gulmarkering (Alt2) per dag/lunch drivs av `alt2_markering`
    - I planeringsflöden finns formler som summerar Alt1/Alt2 över avdelningar
  - Rapport/statistik sammanställer normalkost vs. specialkost per dag/måltid
- Edge‑cases
  - Saknad veckomeny: popup visar text "Ingen meny finns för denna dag eller vecka ännu."
  - Saknad Alt2 för dag: ingen gulmarkering
  - Saknade boendeantal: fall back till avdelningens `boende_antal`

---

## Data & API – legacy vs Unified

- Legacy → Unified mapping (preliminär)
  - Avdelningar (legacy `avdelningar`) → Unified `Unit` (per tenant)
  - Kosttyper (`kosttyper`) → Unified `DietaryType` + `UnitDietAssignment`
  - Registreringar (cellmarkeringar) → Unified vecka‑repo: `weekview_registrations` via `WeekviewRepo.apply_operations()`
  - Boendeantal (`boende_antal`) → Unified vecka‑repo: `weekview_residents_count`
  - Alt2‑dagar (`alt2_markering`) → Unified vecka‑repo: `weekview_alt2_flags` eller Admin Alt2 (`Alt2Repo`) för övergripande val
  - Veckomeny (`veckomeny`) → Unified `Menu` + `MenuVariant` (Alt1/Alt2/Dessert/Kväll per dag/måltid)
- Befintliga Unified‑endpoints
  - Läs (read‑only): `GET /api/weekview?year=YYYY&week=WW&department_id=<uuid>` – svar innehåller `marks`, `residents_counts`, `alt2_days` (+ ETag)
  - Mutationer (ETag/If‑Match):
    - `PATCH /api/weekview` – toggla markeringar per dag/måltid/kosttyp
    - `PATCH /api/weekview/residents` – uppdatera boendeantal
    - `PATCH /api/weekview/alt2` – sätt Alt2‑dagar (lista dagar)
  - Pass B menyval (alternativ):
    - `GET/PUT /admin/menu-choice` – per avdelning/vecka/dag (Alt1/Alt2), med ETag
- Identifierade gap
  - Veckomeny i weekview‑payload: Unified `GET /api/weekview` returnerar inte menytexter än (Alt1/Alt2/Dessert/Kväll). För popup krävs antingen:
    - expandera weekview‑payload med meny (rekommenderat för enkel klient), eller
    - separat endpoint (t.ex. `GET /api/menu?year=YYYY&week=WW&department_id=...`).
  - Namn/etiketter i payload: `department_name` och dietnamn kan behöva join/berikning för UI.

---

## Förslag: Unified Weekview (Kommun)

- UI‑förslag (utseende)
  - Bas: tabellvy med 7 dagar × (Lunch/Kväll) kolumner, rader: "Boende" + en rad per kosttyp
  - Rubrikrad per avdelning (om vi väljer multi‑avdelning på samma sida); initialt kan vi visa en avdelning åt gången för tydlighet på iPad
  - Alt1/Alt2: tydlig visuell markering på lunch (Alt2) – gul bakgrund och liten ikon (t.ex. ⚑) i dagshuvud eller i lunchcell
  - Meny‑popup vid klick på dagshuvud: visar Alt1, Alt2, Dessert, Kväll – stor och läsbar på iPad
  - Responsivitet (iPad först):
    - Sticky kolumnrubriker och horisontell scroll i tabell
    - Alternativ kompaktläge: per‑dag kort stackade vertikalt med Lunch/Kväll rader (kan vara en inställning)
- Navigation
  - Vecka fram/bak (chevron‑knappar) + direkt väljare (week picker)
  - Val av avdelning (dropdown) – URL/params: `?department_id=...&week=WW&year=YYYY`
- Tom‑/fel‑states
  - Ingen meny: visa tomt‑meddelande i popup och länk till Planera/import
  - Ingen data/markeringar: visa nollor och grå placeholder, inga felrutor
  - ETag‑konflikt (412): mjuk toast och automatisk uppdatering av ETag + retry‑knapp

- Tekniskt förslag
  - Route (UI): `/ui/weekview?department_id=<uuid>&week=WW&year=YYYY` (tenant i session)
  - Backend‑anrop
    - Read‑only: `GET /api/weekview` (If‑None‑Match för cache/304)
    - Meny: utöka `GET /api/weekview` att inkludera menytexter per dag/måltid/alt, alternativt nytt `GET /api/menu` med samma parametrar
  - Mutationer (Fas 2)
    - Alt2‑dagar: `PATCH /api/weekview/alt2` (If‑Match)
    - Markeringar per kosttyp: `PATCH /api/weekview` (If‑Match)
    - Boendeantal: `PATCH /api/weekview/residents` (If‑Match)
  - CSRF: befintliga mönster (cookie + header) för PATCH

- Faser
  - Fas 1 (read‑only)
    - Bygg UI som renderar tabell för vald avdelning/vecka (marks, residents_counts, alt2_days)
    - Lägg till meny‑popup (kräver utökad payload eller separat meny‑endpoint)
    - ETag + If‑None‑Match på fetch
  - Fas 2 (mutationer)
    - Toggla markeringar per cell och uppdatera boendeantal via PATCH med If‑Match
    - Sätta Alt2‑dagar via PATCH /weekview/alt2 (blockera helgdag om vi följer menuchoice‑regeln)

- Prioritering
  - MÅSTE för v1 (paritet)
    - Tydlig tabellvy (Lunch/Kväll), rader per kosttyp + Boende
    - Vecka fram/bak, avdelningsval
    - Alt2‑indikering (gulmarkering) + meny‑popup
    - Utskriftvänlig vy
  - KAN senare
    - Kortlayout för små skärmar
    - Sticky headers, summor per dag/måltid
    - Offlinecache (Service Worker) och snabb ETag‑refresh
    - Snabbtangenter, bättre tooltips

---

## Kort sammanfattning (för PR‑beskrivning)

- Kartlagt legacy `veckovy` (HTML/JS/routes) och identifierat kärnfunktioner: tabell per vecka med Lunch/Kväll, markeringar per kosttyp, boendeantal, Alt2‑dagar och meny‑popup.
- Mappat till Unified: använder `GET /api/weekview` (marks/residents/alt2) och föreslår att utöka payload med menytexter, alternativt ny meny‑endpoint.
- Föreslår UI som prioriterar iPad: tabell med sticky/rullbar horisontellt, tydlig Alt2‑indikering, meny‑popup; read‑only först (Fas 1), därefter mutationer med If‑Match (Fas 2).
