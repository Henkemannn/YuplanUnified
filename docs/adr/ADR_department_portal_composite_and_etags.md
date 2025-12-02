# ADR: Avdelningsportal – Komposit-endpoint och ETag-strategi

Datum: 2025-11-22  
Status: Accepted

## 1. Kontext
Vi bygger en Avdelningsportal där en avdelning kan se veckans meny (Alt1/Alt2, dessert, middag/kväll), boendeantal och specialkost, samt göra sitt menyval (Alt1 eller Alt2) per dag. 

Legacy-läget:
- Monolitisk formulär-POST per vecka.
- Ingen ETag, ingen concurrency-kontroll.
- "Markerad" användes som diffus Alt2-indikator och blandade driftflagga med val.

Unified-läget:
- Portalen ska vara ETag-säker, modulär och dela domänmodell med Weekview + Planera.
- Ska kunna växa till fler alternativ än Alt1/Alt2 utan att bryta kontraktet.

## 2. Problem
Data ligger utspridd över flera källor:
- Meny + varianter (Alt1/Alt2/dessert/dinner).
- Weekview-data (residents counts, diets, alt2_lunch driftflagga, menytexter).
- Menyval (vilken alt avdelningen valt: selected_alt).
- Department-fakta (note, ev. defaults).

Behov:
- Samlad vy per vecka för enkel och snabb UI-rendering.
- Concurrency-skydd för menyval (små men frekventa mutationer).
- Minimera roundtrips (ett anrop istället för 4+).
- Tydlig separation mellan drift (produktion) och portalens användarval.

Att undvika:
- Att portalen kör egna SQL mot tabeller utan domänlager.
- Förväxling av weekview alt2_driftflagga med explicit menyval.
- Race conditions vid parallella ändringar.

## 3. Beslut
### Komposit-endpoint
Vi använder `GET /portal/department/week?year&week` som komposit-endpoint. Den hämtar:
- Department + facts (note).
- Weekview-data (dagar med residents, diets, alt2_lunch, menytexter).
- Menyval (selected_alt per dag) – härledd för nu från alt2_flags.

Return-format: `DepartmentPortalWeekPayload` (se `portal/department/models.py` och schema-dokumentet).

Motiv:
- En enda call → enklare och snabbare UI.
- Tydligt kontrakt (versionerat via schema-dokumentet).
- Lättare att lägga på ETag + 304 caching.

### Separata komponent-ETags
Vi bygger ett `etag_map` med logisk separation:
- `menu_choice` – menyvalskomponenten (vilken alt avdelningen valt).
- `weekview` – weekview/meny/residents/diets/alt2 + menytexter.

Portal-ETag skapas genom att hasha hela `etag_map` och prefixa:  
`W/"portal-dept-week:<department_id>:<year>-<week>:<sha1(etag_map)>"`

Mutationer av menyval:
- Ska enbart påverka `menu_choice` och därmed ge ny portal-ETag.

Läsningar i framtiden:
- Kan använda portal-ETag för enkel caching eller (vid behov) komponent-ETags för finare kontroll.

### Alt1/Alt2 som explicit `selected_alt`
Vi inför fältet `choice.selected_alt: "Alt1" | "Alt2" | null`.
Det är skilt från `flags.alt2_lunch` (driftflagga från Weekview).

Motiv:
- Legacy blandade koncept – "markerad" var otydlig.
- Klar separation mellan drift (produktion vad köket kör) och portalens kundval.
- Öppnar för fler alternativ framöver (enum kan utökas utan semantisk konflikt).

### Read-only statistik i portalen
`residents` och `diets_summary` kommer direkt från Weekview/Planera och är read-only i portalen.

Motiv:
- Undvika att portalen blir ännu en skrivare av produktionsdata.
- Tydlig ansvarsfördelning: Weekview/Planera hanterar produktion och statistik, Portalen hanterar val/önskningar.

### Kommande mutationer använder If-Match på menu_choice
Framtida endpoint `POST /portal/department/menu-choice/change` ska:
- Kräva `If-Match` (eller body-fält `if_match`) baserat på `etag_map.menu_choice`.
- Returnera 412 vid mismatch (optimistic concurrency).

Motiv:
- Isolation av concurrency till den del som faktiskt förändras ofta.

## 4. Alternativ övervägda
**Alt A: Många små endpoints istället för komposit**  
Exempel: separata GET för meny, residents, diets, val.  
Nackdelar: Mer komplex klient, fler roundtrips, ETag-hantering svårare och fragmenterad.

**Alt B: Endast portal-ETag (ingen komponent-separation)**  
Nackdelar: Små menyvalsmutationer invalidierar hela portalens cache, svårare att se vad som ändrats.

**Alt C: Binda menyval direkt till weekview alt2_flag**  
Nackdelar: Blandar drift med kundval, blockerar framtida fler-alternativsmodell.

## 5. Konsekvenser
Positiva:
- ✅ Portal-UI kan hämta all data i ett enda GET-anrop.
- ✅ Menyvalsmutationer kan införas utan att röra Weekview/Planera-lagret.
- ✅ ETag-hantering blir tydlig: `menu_choice` ändras oftare än `weekview`.
- ✅ Klar separation: produktion vs avdelningsval.

Negativa / trade-offs:
- ⚠ Fler lager av ETag (komponent + portal) kräver bra testtäckning.
- ⚠ Mer logik i kompositservice → måste hållas ren, dokumenterad och testad.

## 6. Implementation Status (Sanity-check)
Existerande kod som realiserar besluten:
- Schema: `docs/department_portal_week_schema.md`.
- Modeller: `portal/department/models.py`.
- Komposit-service: `portal/department/service.py` (funktion `build_department_week_payload`).
- Endpoint: `portal/department/api.py` (`GET /portal/department/week`).
- Test: `tests/portal/test_department_portal_week_endpoint.py` (assertar menytexter, val, ETag/304).
- ETag-strategi: portal ETag genereras som hash av `etag_map` i endpointen (inkluderar menyval + weekview + menytexter).

## 7. Framtida Riktning (Scope framåt)
Denna ADR låser principer inför:
- Auth-fas: Byta från headers till claims/JWT i portalen.
- Mutation-fas: Införa explicit menyvalspersistens & `If-Match`-baserad concurrency.
- UI-fas: Färre anrop, reaktiv uppdatering av val utan att tappa statistik.

Utanför scope just nu:
- Persistens av historik för menyval.
- Granulär komponent-ETag-exponering i API-svar (möjlig förbättring senare).
- Avancerad fallback för menytexter (ex. overrides på enskild dag).

## 8. Beslutsmotivering (Sammanfattning)
Vi väljer en komposit-endpoint med separata komponent-ETags för att optimera portalens enkelhet, prestanda och tydlighet i ansvar. Genom att isolera menyval i egen ETag-del kan vi skala mutationer och concurrency utan att kassera övrig cache. Separationen mellan driftflagga (alt2_lunch) och explicit kundval (selected_alt) gör modellen framtidssäker för fler än två alternativ.

---
Referens: Detta dokument beskriver redan implementerad funktionalitet; status är "Accepted".
