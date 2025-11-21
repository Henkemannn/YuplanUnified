# Planera-modulen – Funktionsgenomgång (köket)

Senast uppdaterad: 2025-11-20

## Mål och nytta
- Förenkla daglig produktion i köket: rätt antal portioner per rätt och specialkost.
- Minimera fel och pappersarbete via tydliga vyer och utskrifter.
- Återanvänd Weekview-data som “source of truth” (boendeantal, markeringar, specialkost, alt2-dagar, menytexter).

## Primära användare (personas)
- Köksplanerare/kökspersonal: Ser dagens/veckans plan, skriver ut produktionslistor, gör mindre justeringar.
- Kostansvarig/admin: Sätter grunddata (meny, specialkoststandard), följer upp statistik och kvalitet.

## Viktiga användarflöden
1. Daglig planering (standard):
   - Välj datum/site/ev. avdelningsfilter → se summeringar per måltid (lunch/kväll).
   - Se fördelning: Normal, specialkost per diet, samt Alt1/Alt2 beroende på dagens flagg.
   - Skriv ut “Produktionslista” (1–2 A4) med totalsiffror och kommentarer.
2. Veckovy planering (överblick):
   - För varje veckodag: kort summering per måltid och specialkost.
   - Export som CSV för uppföljning/inköp.
3. Småjusteringar inför service:
   - Tillfällig justering samma dag (t.ex. +2 normal lunch) med tydlig visning att detta ej ändrar Weekview-källdata.
4. Utskrift och export:
   - “Produktionslista (dag)” och “Veckoöversikt” som utskriftsvänliga vyer (print CSS) samt CSV-export.

## Omfattning (MVP)
- Läsning: Återanvänd Weekview (residents, diets, marks, alt2, menytexter) för att räkna produktionsvolymer.
- Visning: Dagsvy + Veckovy med tydliga totalsiffror per måltid och diet.
- Utskrift: Enkel, iPad-vänlig layout, inga horisontella scrollar i normalfallet.
- Export: CSV för vecka.
- Inga mutationer i MVP (justeringar kan vara en tilläggsfas).

## Datakällor och beräkningar
- Weekview.service.days per avdelning:
  - `residents[meal]` → boendeantal per dag & måltid.
  - `diets[meal][]` → {diet_type_id, resident_count, marked}.
  - `alt2_lunch` → flaggar Alt2-dag (kan påverka uppdelning).
  - `menu_texts` → meny för etiketter (Alt1/Alt2, ev. dessert).
- Beräkning per dag & måltid:
  - `special_diets_sum = sum(resident_count where marked == true)`
  - `normal = max(0, residents - special_diets_sum)`
  - Summera över avdelningar till köksnivå (site) och presentera både per-avdelning och totalsumma.

## API-förslag (read-only)
- `GET /api/planera/day?site_id&date&department_id?`
  - Returnerar planeringsobjekt för ett datum: per måltid (lunch/kväll), per avdelning och totalsumma.
  - Inkluderar menytexter (Alt1/Alt2) för etikettering.
- `GET /api/planera/week?site_id&year&week&department_id?`
  - Veckosummering som ovan, per dag.
- ETag/Cache:
  - Weak ETag på site+date respektive site+week, härledd från underliggande Weekview-versioner per avdelning.
  - Endast 200/304 (inga mutationer).

## UI-vyer
1. Dagsvy (Planera / Dag):
   - Header: Datum, Site, ev. avdelningsfilter.
   - Sektion per måltid (Lunch/Kväll):
     - Meny Alt1/Alt2 (om tillgängligt), Alt2-indikator.
     - Tabell per avdelning: Normal, Specialkost per diet, Summa.
     - “Totalsumma kök”: summerad rad i slutet.
   - Knapp: “Skriv ut produktionslista (dag)”.
2. Veckovy (Planera / Vecka):
   - Tabell 7×2 (dag × måltid) med totalsiffror och korta etiketter.
   - Knapp: “Exportera CSV (vecka)”.

## Roller & behörighet
- `viewer`: kan se planera-vyer (read-only).
- `editor/admin`: samma som viewer, eftersom MVP är read-only.
- Framtida fas: justeringsrättigheter för editor/admin.

## Icke-funktionella krav
- Prestanda: läsningar ska bygga på batch-hämtning av Weekview per site + caching/ETag för att undvika onödig belastning.
- Tillgänglighet: tydliga tabbföljder, ARIA-etiketter på knappar och tabeller.
- Utskrift: separat print-stylesheet, kompakt med bibehållen läsbarhet.

## Teststrategi
- Enhetstester för aggregering (dag + vecka, alt2, specialkost, normal).
- API-snapshot/kontraktstester (`/api/planera/day|week`).
- UI-renderingstester (Jinja) för dagsvy och veckovy.
- E2E-rök: navigera, filtrera, skriv ut (kontrollera att print CSS tillämpas).

## Fasning (förslag)
**Fas P1 (MVP, read-only)**
- API: `/api/planera/day`, `/api/planera/week`.
- UI: Dagsvy + Veckovy (read-only), utskrift + CSV.
- Flagga: `ff.planera.enabled`.

**Fas P2 (lätta justeringar, ej Weekview-källa)**
- Tillfälliga justeringar per dag/måltid (t.ex. +N), sparas separat (ej i Weekview), nollställs nästa vecka.
- Visuell markering “justerad”. Export inkluderar justeringar.

**Fas P3 (integrationer/avancerat)**
- Export till köksproduktionssystem.
- Ytterligare etiketter (allergen, portionsstorlek) och multi-variant för middag om tillämpligt.
- Roller: finare-granulär behörighet och audit-logg.

## Acceptanskriterier (P1)
- Givet site + datum visas korrekta totalsiffror per måltid, per avdelning och som kökssumma.
- Specialkost summeras endast när markeringar finns; normal = boende – sum(specialkost).
- Alt2-indikator och etiketter hämtas från menytjänst/Weekview om tillgängligt.
- Utskrift (dag) är läsbar utan horisontell scroll i A4-porträtt.
- CSV (vecka) innehåller dag, måltid, per-avdelning och totalsummor.

## Öppna frågor
- Behöver middag också Alt2 eller andra varianter i vissa kommuner?
- Hur ska tillfälliga justeringar arkiveras (per site/år/vecka/dag)?
- Ska utskriften visa menytexter eller enbart kvantiteter i MVP?
