# YUPLAN FUTURE LAB
## RFC — YUPLAN NUTRITION
### Näringsberäkning, måltidsoptimering och framtida kostrådgivning

**Status:** Future Lab — idé dokumenterad, ingen implementation beställd  
**Datum:** 2026-10-09  
**Område:** Yuplan Platform / Yuplan Work / Yuplan Home  
**Prioritet:** Efter Yuplan 1.0 och efter stabil Ingredient Library / receptnormalisering  
**Implementation:** Beslutas separat inom Yuplan Unified

---

# 1. Sammanfattning

Yuplan Nutrition är ett framtida gemensamt beräkningslager som använder samma strukturerade matdata som Yuplan redan bygger för recept, komponenter, maträtter, menyer, produktion, inköp och kalkyl.

Grundprincip:

> Om Yuplan vet vilka ingredienser som ingår, hur mycket som används och hur många portioner receptet ger, kan Yuplan också beräkna näringsinnehållet.

Nutrition ska därför inte bli en separat receptvärld eller en separat verksamhetsmodul med egen matmodell.

Den långsiktiga riktningen är:

```text
Ingredient / råvara
-> Recipe
-> Component
-> Dish / Composition
-> Meal
-> Day / Week menu
-> Nutrition projection
```

Samma matmodell ska kunna konsumeras av flera motorer:

```text
Production Engine  -> Hur mycket ska produceras?
Purchasing         -> Vad behöver köpas?
Cost Engine        -> Vad kostar det?
Nutrition Engine   -> Vad innehåller måltiden näringsmässigt?
```

---

# 2. Unified-beslut om placering i roadmap

Nutrition ska **inte** läggas in före Yuplan 1.0.

Rekommenderad ordning:

1. **Yuplan 1.0**
   - Kommun pilotklar
   - Offshore pilotklar
   - nuvarande Builder / Planera seam stabil

2. **Builder 1.1 / Ingredient Foundation**
   - canonical Ingredient Library
   - stabil ingrediensidentitet
   - stabila receptmängder
   - normaliserade måttenheter
   - återanvändbara ingredienser mellan recept
   - tydlig portionsdefinition / yield-grund

3. **Nutrition P0**
   - extern nutrition mapping per ingredient
   - energi + grundläggande makronutrienter
   - receptsumma
   - per portion
   - tydlig hantering av saknade/osäkra värden

4. **Nutrition P1**
   - Component -> Dish -> komplett måltid
   - meny / publicerad nutritionprofil
   - portionsanpassning

5. **Nutrition P2+**
   - avancerad tillagningsjustering
   - nutritionmål / veckomenyanalys
   - professionell kostplanering
   - eventuell individnivå först efter separat säkerhets/regulatorisk bedömning

## Viktig slutsats

Nutrition P0 är inte ett monsterprojekt **när Ingredient Library och receptdata är stabila**.

Den svåra delen är främst datakvalitet, identitet, enheter, mapping och spårbarhet — inte själva matematiken.

---

# 3. Canonical kopplingspunkt

Näringskoppling ska i första hand ligga på **canonical Ingredient**, inte direkt på varje Dish eller Component.

Exempel:

```text
Ingredient: Nötfärs
nutrition_source = livsmedelsverket
external_food_id = ...
source_version = ...
match_status = verified
```

Därefter kan samma canonical Nötfärs återanvändas i:

- Köttbullar
- Pannbiff
- Köttfärssås
- Lasagne
- andra recept

Det undviker duplicerade nutritionkopplingar och skapar en stark gemensam matmodell.

## Arkitekturreservation när Ingredient Library byggs

När Ingredient Library designas ska modellen medvetet kunna bära framtida metadata som:

- `nutrition_source`
- `external_food_id`
- `nutrition_source_version`
- `nutrition_match_status`
- eventuell confidence / verification-status

Detta betyder **inte** att Nutrition Engine ska implementeras samtidigt.

Poängen är bara att undvika en onödig datamodellsmigration senare.

---

# 4. Nutrition P0 — rekommenderad första implementation

P0 ska vara liten, deterministisk och reproducerbar.

## Scope

- koppla Ingredient till en extern näringspost
- hämta nutrition per 100 g eller relevant basenhet
- beräkna receptets totalsumma
- beräkna per portion
- visa:
  - kcal
  - kJ
  - protein
  - fett
  - kolhydrater
  - eventuellt fiber/salt om källan är komplett
- markera:
  - saknade mappings
  - osäkra mappings
  - ofullständig nutritionprofil

## Grundformel

För varje ingredient:

```text
ingredient_quantity_g
× nutrient_per_100g
/ 100
```

Summera samtliga ingredients och dividera vid behov med receptets portionsantal.

## Viktigt

P0 ska inte försöka lösa:
- vitaminretention
- avancerad tillagningsförlust
- fettupptag
- rå/tillagad viktmodell
- individbaserad rådgivning

---

# 5. Datakällor

Möjliga källor att utvärdera:

## Livsmedelsverket

Naturlig kandidat som svensk primärkälla.

Relevant för:
- svenska råvaror
- svensk offentlig måltidsverksamhet
- Kommun
- nordisk produktpositionering

Licens, versionshantering och källhänvisning måste granskas innan kommersiell implementation.

## USDA FoodData Central

Möjlig kompletterande internationell källa.

## Open Food Facts

Särskilt intressant för Yuplan Home där användaren kan välja konkreta konsumentprodukter / streckkoder.

Datakvaliteten är varierande och måste markeras korrekt.

## Leverantörsdata / egna värden

Professionella kök ska på sikt kunna använda:
- grossistdata
- produktdatablad
- leverantörsdata
- producentdata
- egna registrerade värden

Datakälla och beräkningsmotor ska vara separerade.

---

# 6. Spårbarhet och snapshots

Nutrition får inte reduceras till ett enda sparat kcal-värde utan provenance.

För ett beräknat värde bör Yuplan kunna härleda:

- ingredient identity
- extern livsmedelspost
- datakälla
- datakällans/versionens identitet
- matchningsstatus
- beräkningsmetod
- om profilen är komplett eller uppskattad

Historiska publicerade menyer får inte okontrollerat ändra sina nutritionvärden bara för att en extern databas senare uppdateras.

När Nutrition går från prototyp till professionell funktion måste versions-/snapshotstrategin därför kopplas till Yuplans publiceringsmodell.

---

# 7. Yuplan Kommun

Nutrition kan skapa tydligt professionellt värde i Kommun.

Fokus ska inte vara bantning eller kalorireduktion.

Mer relevanta användningsfall:

- energi per måltid
- protein per måltid
- veckomenyans näringsprofil
- måltider som avviker från verksamhetens definierade mål
- stöd till kostchef / dietist
- jämförelse av menyförslag
- energitäthet och protein i äldreomsorg

Mål/gränser ska komma från fastställd verksamhets- eller professionell policy, inte från hårdkodade Yuplan-antaganden.

Exempel på framtida Builder-vy:

```text
Vecka 12 — näringsprofil

Energi        ✓
Protein       ⚠ 2 luncher under verksamhetens mål
Fiber         ✓
Fisk          2 / vecka
Vegetariskt   2 / vecka
```

Nutrition ska vara ett analyslager ovanpå canonical meny/receptdata — inte en ny menytruth.

---

# 8. Yuplan Home

Home är ett starkt framtida användningsfall eftersom samma motor kan ligga under:

```text
Veckomeny
-> näringsanalys
-> portionsanpassning
-> inköpslista
-> beställning
```

Möjliga funktioner senare:

- näringsvärde på recept
- energimål
- makronutrientmål
- portionsjustering
- veckomenyanalys
- produkt-specifik nutrition via exempelvis Open Food Facts
- shoppinglist / retailer integration

Viktig skillnad:

Planerad meny = planerat näringsinnehåll.

Det är inte samma sak som faktiskt intag.

Faktiskt intag kräver separat registrering och ska inte antas av systemet.

---

# 9. Yuplan Offshore

Möjliga framtida användningsfall:

- nutrition för dagens lunch/middag
- måltidsprofil under längre rotationer
- energi/protein/makroöversikt
- nutritioninformation tillsammans med publicerad meny

Offshore är inte första implementation för Nutrition.

---

# 10. Hotell / Bankett

Nutrition kan senare konsumera samma event/menu/component-model.

Exempel:

1300 gäster, trerättersmeny:

- förrätt nutrition
- huvudrätt nutrition
- dessert nutrition
- total menyprofil
- alternativ kost / vegetarisk menyprofil

Ingen separat bankett-nutritionmotor ska skapas.

---

# 11. P0–P4 utvecklingsnivåer

## P0 — Grundläggande näringsberäkning

**Storlek: liten–medel när Ingredient Foundation är stabil.**

- Ingredient -> nutrition mapping
- nutritiondata
- receptsumma
- per portion
- kcal/kJ/macros
- missing/uncertain state

Teknisk beräkningsprincip är enkel.

Produktionsmässigt robust P0 kräver främst datakvalitet, provenance och UX för mapping.

## P1 — Kompletta måltider

**Storlek: medel.**

- Component aggregation
- Dish aggregation
- meal aggregation
- portionsanpassning
- publicerad nutritionprofil

## P2 — Avancerad beräkning

**Storlek: stor.**

- tillagningsmetod
- vattenförlust/upptag
- fettförlust/upptag
- tillagningssvinn
- ätbar andel
- rå/tillagad vikt
- yield
- retentionsfaktorer
- fler mikronutrienter

Systemet bör då kunna skilja på exempelvis:

- grundberäknat näringsvärde
- tillagningsjusterat näringsvärde

## P3 — Näringsplanering

**Storlek: medel–stor.**

- energi-/makromål
- dagsanalys
- veckoanalys
- menyoptimering
- verksamhetsprofiler
- kostansvarig/dietist-stöd

## P4 — Professionell individnivå

**Storlek: mycket stor + separat regulatoriskt spår.**

- individanpassade planer
- professionella mål per person
- faktiskt intag
- rådgivning
- dietistarbetsyta
- eventuell koppling Home <-> professional

Om Yuplan går in i individuell hälsorådgivning eller behandling måste frågor om:
- hälsodata
- professionellt ansvar
- evidens
- patientsäkerhet
- medicinteknisk reglering

utredas separat innan implementation.

---

# 12. AI-princip

Nutrition Engine ska vara **deterministisk**.

AI får användas som stöd, exempelvis för:

- förslag på ingredient -> food database match
- hitta receptingredienser som saknar mapping
- menyförslag
- portions-/komponentförslag
- alternativa ingredients

AI får inte:
- hitta på näringsvärden
- göra osäkra mappings till verifierad truth utan granskning
- ersätta reproducerbara beräkningsregler

Beräkningarna måste vara granskningsbara och reproducerbara.

---

# 13. Arbetsbedömning

## När Ingredient Library är färdig

Rimlig grov uppskattning:

- enkel P0-prototyp: några utvecklingsdagar
- robust P0 med mapping-UX, källa, provenance, missing-state och tester: ungefär ett par fokuserade utvecklingsveckor
- P1: separat medelstor gate
- P2/P3: större produktområden, byggs endast efter validerat kundbehov
- P4: eget framtida program, inte en vanlig feature

Detta är planeringsuppskattning, inte en tidscommitment.

---

# 14. Strategiskt värde

Nutrition stärker varför Yuplan bör bygga en canonical Ingredient-model.

Samma Ingredient kan på sikt bära eller länka:

```text
identity
+ recipe quantity semantics
+ price
+ supplier/product mapping
+ allergen information
+ purchasing information
+ nutrition mapping
```

Det skapar hävstång över hela plattformen.

Nutrition är därför strategiskt starkast som **ytterligare ett beräkningslager på samma Food Knowledge Model**, inte som en egen vertikal datamodell.

---

# 15. Beslut 2026-10-09

**SAVE / FUTURE LAB.**

Ingen kod ändras i nuvarande Yuplan 1.0-arbete på grund av Nutrition-idén.

Beslut:

1. Bevara Nutrition som separat strategiskt Future Lab-spår.
2. Bygg inte Nutrition före Yuplan 1.0 pilotclosure.
3. När Ingredient Library designas ska Nutrition-future-proofing ingå.
4. P0 är första möjliga implementation efter stabil Ingredient + Recipe quantity/unit foundation.
5. Kommun och Home är de starkaste tidiga användningsfallen.
6. P0 ska vara deterministisk och begränsad.
7. P2/P3/P4 byggs bara efter verkligt användar-/kundbehov.
8. Ingen AI-genererad nutrition truth.
9. Ingen separat nutrition-receptmodell.
10. Ingen implementation order från detta dokument.

---

# 16. Öppna frågor inför framtida technical census

När Nutrition blir aktivt bör Unified först kartlägga:

- nuvarande Ingredient/Recipe-modell
- återanvändning av ingredients mellan Components
- quantity/unit-normalisering
- portionsdefinition
- yield
- lämplig nutrition source abstraction
- Livsmedelsverkets licens/API/versionering
- Open Food Facts licens och kvalitetsmodell
- snapshot/provenance model
- missing/uncertain mapping UX
- publicerad meny nutrition snapshot
- professionell kvalitetsnivå för Kommun
- om och när nutrition-data behöver supplier/product-level identity

---

# 17. One-line roadmap

**Yuplan 1.0 -> Ingredient Library + Recipe normalization -> Nutrition P0 -> complete-meal P1 -> advanced nutrition only when real customer value justifies it.**
