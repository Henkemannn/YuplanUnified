# Planera 2.0 – Kommun UX-målbild

**Status:** Living document / produktmålbild  
**Version:** v0.1  
**Senast uppdaterad:** 2026-09-08  
**Aktiv utvecklingsbranch:** `feat/planera-app-shell-2026-03-03`

Detta dokument är den aktuella UX- och produktmålbilden för Planera 2.0 i Kommun-spåret. Det ska uppdateras löpande när vi lär oss mer i mockups, tester och implementation.

---

## 1. Syfte

Planera 2.0 ska göra den dagliga produktionsplaneringen i ett kommunalt produktionskök enkel, tydlig och säker utan att försöka fatta professionella måltidsbeslut åt användaren.

Den primära mentala modellen är:

> **Välj dag → se dagens mat → markera vilka som inte kan äta respektive normalkost → Yuplan räknar → öppna det produktionsunderlag du behöver.**

Planera ska vara ett besluts-, räknings- och produktionsverktyg. Det ska inte vara ett expertsystem som automatiskt avgör vem som kan eller inte kan äta en rätt.

---

## 2. Grundprinciper

1. Planera börjar med **dag/datum**.
2. Publicerad meny för vald dag visas direkt.
3. Användaren väljer vilken måltid eller produktionsinformation som ska planeras eller visas.
4. För varje menyalternativ anger användaren vilka registrerade avvikelse-/kravfamiljer som **inte kan äta normalkosten som den är**.
5. Om en huvudavvikelse väljs, t.ex. `Timbal`, ska alla kombinationsgrupper som innehåller Timbal räknas med automatiskt.
6. Överlappande kombinationer får aldrig dubbelräknas.
7. Yuplan fattar aldrig automatiskt beslutet att en person/grupp inte kan äta rätten.
8. Builder-data får ge **förslag/information**, men användaren avgör alltid vilka avvikelser som faktiskt ska registreras i planeringen.
9. Planera ska fungera fullt även om kunden aldrig bygger detaljerade recept, allergener eller framtida texturdata i Builder.
10. Samma planeringsbeslut ska återanvändas genom hela verksamheten. Olika produktionsanvändare ska inte behöva göra samma markeringar igen.
11. Produktionsinformation organiseras efter **vad användaren vill se**, inte efter vilka fysiska kök/stationer som producerar vad.
12. Information ska visas progressivt: enkel översikt först, detaljer vid behov.
13. Faktiskt producerad specialkost ska kunna markeras och fortsätta till veckovy och statistik.
14. Tillägg ska vara konfigurerbara och bara visas där de är relevanta.
15. Arkitekturen ska vara generell nog att återanvändas i Offshore, Hotel/Banquet/Event och senare Yuplan Home.

---

## 3. Viktig domänprincip: normalkost först

Normalkost är baslinjen.

Planera ska inte börja med en separat fråga om "normalkost eller specialkost". Den naturliga arbetsuppgiften är i stället:

> **Planera tisdagens lunch.**

För varje rätt bedömer användaren sedan vilka registrerade kravgrupper som inte kan äta rätten som normalkost.

Detta skapar därefter produktionsvyer för:

- Normalkost
- Specialkost / specialanpassningar
- Tillägg
- Utskick / mottagande enheter

---

## 4. Exempelscenario som används i UX-arbetet

Alla mockups ska i första hand använda samma scenario så att siffror och beteenden kan följas genom hela flödet.

**Datum:** Tisdag 8 september

### Lunch

**Alternativ 1**  
Fläskkarré · potatismos · gräddsås

**Alternativ 2**  
Kokt torsk · äggsås · kokt potatis

**Mottagande enheter:** 18

- 12 mottagande enheter har valt alternativ 1.
- 6 mottagande enheter har valt alternativ 2.

Registrerade behov/avvikelser i verksamheten kan exempelvis vara:

- Timbal
- Timbal + Laktos
- Timbal + Glutenfri
- Grov paté
- Laktos
- Glutenfri
- Flytande kost

En registrerad avvikelse är inte automatiskt en produktionsavvikelse för varje rätt.

Exempel:

- En person med Grov paté kan behöva tas bort från normalkost för fläskkarré.
- Samma person kan kanske äta kokt torsk oförändrad.

Det är därför användarens bedömning av den aktuella rätten som är styrande.

---

## 5. Builder som rådgivande kunskapskälla

Om en rätt är en Builder-dish/composition och har bakomliggande strukturerad information ska Planera visa denna information vid rätten.

Exempel:

**Fläskkarré · potatismos · gräddsås**

Registrerad information för rätten:

- Laktos
- Timbal
- Grov paté
- Flytande kost

Denna information kan i framtiden komma från flera typer av Builder-data, exempelvis:

- EU:s 14 allergener
- recept-/ingrediensdata
- texturinformation
- andra strukturerade kostegenskaper

### Regler

- Informationen är ett **förslag/advisory signal**.
- Användaren väljer själv vilka förslag som ska accepteras.
- Inget förslag får automatiskt markera en avvikelse som faktisk produktionsavvikelse.
- Ingen Builder-information får vara ett krav för att kunna använda Planera.
- Fri menytext utan Builder-referens ska fungera lika väl, men utan automatiska förslag.

Exempel:

Yuplan kan visa att Builder har registrerat mjölk/laktosrelaterad information för gräddsåsen. Om köket vet att all gräddsås den dagen görs laktosfri för samtliga behöver användaren inte acceptera `Laktos` som avvikelse.

---

## 6. Huvudavvikelse och kombinationsgrupper

Användaren ska arbeta på en enkel huvudnivå under själva planeringen.

Exempel:

- `Timbal 8 [+]`
- `Grov paté 4 [+]`
- `Laktos 9 [+]`
- `Glutenfri 6 [+]`
- `Flytande kost 2`

### Plus-tecknet

Om en huvudavvikelse innehåller underliggande kombinationsgrupper visas ett `+`.

När användaren öppnar `Timbal 8 [+]` kan specifikationen rullas ut:

- Timbal – 5
- Timbal + Laktos – 2
- Timbal + Glutenfri – 1

Detta är endast en förklaring av vilka grupper som ingår. Användaren ska inte behöva välja varje kombination separat.

### Urvalsregel

Om användaren väljer `Timbal` ska Yuplan inkludera alla grupper där den atomära avvikelsen `Timbal` ingår.

Exempel:

- Timbal = 3
- Timbal + Laktos = 2
- Laktos = 4

Väljs `Timbal` blir 5 personer exkluderade från normalkost.

Om användaren därefter också väljer `Laktos` ska total unik exkludering vara 9, inte 11.

Detta kräver att Planera räknar på unika kohorter/individer/grupper och atomära krav, inte på enkla summerade etiketter.

---

## 7. UX-flöde – storyboard

Målbilden ska först valideras som en sammanhängande storyboard innan produktionskod byggs.

### Skärm 1 – Planera start / vald dag

Syfte: ge omedelbar orientering utan informationsöverlastning.

Visar:

- sidtitel `PLANERA`
- kompakt veckonavigering
- vald dag/datum
- dagens måltider som stora touchvänliga kort

Exempel på kort:

- Lunch
- Kväll
- Dessert
- Tillägg

Lunchkortet kan visa:

- alternativ 1
- alternativ 2
- antal mottagande enheter
- totalt antal portioner
- tydlig åtgärd `Planera`

Det ska inte finnas stora tabeller, statistik eller detaljerad specialkostinformation på startskärmen.

### Skärm 2 – Lunch / dagens alternativ

Visar vald lunch och samtliga alternativ.

För varje alternativ:

- rättnamn/menytext
- antal mottagande enheter
- antal personer/portioner
- eventuell registrerad Builder-information
- knapp/åtgärd `Planera alternativ`

Builder-information visas diskret och ska inte dominera rätten.

### Skärm 3 – Bedöm normalkosten

Detta är kärnsteget.

Rubrik/fråga:

> **Vilka kan inte äta den här rätten som den är?**

Visar verksamhetens registrerade huvudavvikelser som tydliga touchbara val.

Exempel:

- Timbal 8 [+]
- Grov paté 4 [+]
- Laktos 9 [+]
- Glutenfri 6 [+]
- Flytande kost 2

Om Builder har registrerat relevant information kan dessa alternativ märkas diskret som förslag, exempelvis med en liten symbol.

Användaren väljer själv vilka som faktiskt ska exkluderas från normalkosten.

### Skärm 4 – Kontroll före bekräftelse

Innan planeringen låses/sparas ska användaren se konsekvensen av valen.

Exempel:

- Totalt: 182 personer
- Normalkost: 171
- Anpassningar: 11

Visa valda huvudavvikelser och möjlighet att öppna kombinationsspecifikation via `+`.

Undvik tekniska systemmeddelanden om dubbelräkning. Det viktiga är att siffrorna är korrekta och begripliga.

Primär åtgärd:

`Bekräfta planering`

### Skärm 5 – Lunch / produktionsöversikt

Efter bekräftad planering visas en sammanhållen produktionsöversikt.

Föreslagen navigation:

- Översikt
- Normalkost
- Specialkost
- Tillägg
- Utskick

Exempel:

**Alt 1 – Fläskkarré**

- 171 normalkost
- 11 specialanpassningar

**Alt 2 – Kokt torsk**

- 89 normalkost
- 2 specialanpassningar

### Skärm 6 – Produktionsunderlag / Normalkost

Visar endast information relevant för normalproduktionen.

För varje rätt/alternativ:

- total normalkost
- mottagande enheter
- portioner per mottagande enhet

Specialkostdetaljer ska inte belasta denna vy.

### Skärm 7 – Produktionsunderlag / Specialkost

Här visas detaljerade kombinationer eftersom de är relevanta för produktionen.

Exempel:

**Timbal – 8 portioner**

- Timbal – 5
- Timbal + Laktos – 2
- Timbal + Glutenfri – 1

Därefter destination/mottagande enhet och antal.

Produktionsanvändaren ska kunna markera faktiskt producerat/klart.

---

## 8. Progressiv informationsvisning

Planera ska undvika den klassiska adminpanelens informationsöverlastning.

Princip:

> Visa bara det användaren behöver för nästa beslut.

Exempel:

- Startskärm: dag + måltider
- Måltid: rätter + volym + eventuell diskret Builder-info
- Planering: huvudavvikelser
- `+`: kombinationsdetaljer
- Normalkostvy: normalkostvolymer och destinationer
- Specialkostvy: kombinationer och destinationer

Detaljer ska inte synas bara för att systemet råkar ha dem.

---

## 9. Tillägg

Tillägg ska inte hårdkodas som separata fasta funktioner för exempelvis Sallad eller Mos.

Använd en konfigurerbar tilläggsmodell kopplad till måltid/service.

Exempel:

- Sallad
- Mos
- Pasta istället
- Ris istället
- Bröd
- kundspecifika val

Ett tillägg kan ha:

- antal per mottagande enhet
- lunch/kväll eller annan service
- notering

Om kunden inte använder tillägg ska sektionen vara minimal eller helt döljas.

---

## 10. Producerat → Veckovy → Statistik

Planera måste behålla den viktiga operativa kedjan från befintligt Kommun-system.

Skillnad ska kunna göras mellan:

1. registrerat behov
2. planerad produktionsavvikelse
3. faktiskt producerad specialkost

Målflöde:

> **Behov registrerat → Planering gjord → Produktionsunderlag → Producerad/markerad → Veckovy → Statistik / debiteringsunderlag**

Kunder kan använda statistiken på olika sätt, exempelvis intern uppföljning eller separat debitering. Yuplan ska därför leverera korrekt operationell data utan att hårdkoda hur kunden ekonomiskt använder den.

---

## 11. Begrepp

### Mottagande enhet

Vårdavdelning, boende eller annan enhet som tar emot mat.

Använd detta begrepp när det går för att undvika sammanblandning med interna köksstationer.

### Produktionsvy

En vy över en viss typ av produktionsinformation, exempelvis Normalkost eller Specialkost.

### Huvudavvikelse

En atomär krav-/avvikelsefamilj, exempelvis Timbal, Laktos eller Glutenfri.

### Kombinationsgrupp

En registrerad grupp som består av flera huvudavvikelser, exempelvis `Timbal + Laktos`.

---

## 12. Vad Planera INTE ska göra i Kommun MVP

- Inte kräva att kunden bygger recept först.
- Inte kräva allergen- eller texturdata i Builder.
- Inte automatiskt avgöra vem som kan äta en rätt.
- Inte konfigurera vilken fysisk köksstation som ansvarar för en viss produktion.
- Inte hårdkoda Alt1/Alt2 som generell Planera Core-domän.
- Inte visa alla tillgängliga detaljer på varje skärm.
- Inte skapa ett separat specialkostbeslut för varje produktionsstation.
- Inte bygga om Planera Core till en kommun-specifik motor.

---

## 13. Arkitekturkoppling

Builder är långsiktigt Source of Truth för matkunskap:

`Components → Dishes / Compositions → Menus → Published Menu`

Planera 2.0 konsumerar verksamhetskontext och effektiv meny via adapters.

Builder kan i framtiden bidra med rådgivande egenskaper från:

- composition
- components
- recipes
- allergens
- texture/production metadata

Men Planera Core ska förbli verksamhetsneutral.

Kommun-specifika begrepp och beslut hör hemma i Kommun-adaptrar/application layer, inte i den generiska kärnan.

---

## 14. UX-kvalitetskrav

Planera ska bli referensnivå för nya Yuplan-gränssnitt.

Prioriteringar:

- iPad/tablet först
- stora tryckytor
- tydlig visuell hierarki
- lugn startsida
- hög informationsdensitet först när arbetsuppgiften kräver det
- modernt men professionellt uttryck
- minimalt med klassisk admin-tabellkänsla
- konsekventa statusar
- bra tomlägen
- stöd för light/dark i framtida designsystem
- språkneutral intern modell, senare sv/no/en

---

## 15. Mockup-gate

Nästa utvecklingsgate är **inte produktionsimplementation**.

### `PLANERA-KOMMUN-UX-1 – målbild och huvudflöde`

Först ska följande mockups/prototypskärmar valideras:

1. Planera start / vald dag
2. Lunch / dagens alternativ
3. Bedöm normalkosten – "Vilka kan inte äta den här rätten som den är?"
4. Kontroll före bekräftelse

När detta känns självklart går vi vidare med:

5. Produktionsöversikt
6. Normalkost
7. Specialkost
8. Tillägg
9. Utskick
10. Veckovy / statistik

Ingen backend- eller produktionslogik ska ändras enbart för att göra mockupen.

---

## 16. Beslut som är låsta i v0.1

- Dag → måltid → bedöm normalkost är huvudflödet.
- Användaren är alltid beslutsfattare för faktisk avvikelse.
- Builder är rådgivande, aldrig auktoritär i detta steg.
- Planera fungerar utan Builder-detaljdata.
- Huvudavvikelser används vid planering.
- Kombinationsgrupper visas bakom `+` och räknas automatiskt in under huvudavvikelsen.
- Överlapp får aldrig dubbelräknas.
- Samma beslut återanvänds i alla produktionsvyer.
- Produktion organiseras efter informationsbehov, inte köksstation.
- Faktiskt producerat fortsätter till veckovy och statistik.

---

## 17. Öppna frågor för kommande versioner

Dessa ska inte blockera UX-1:

- exakt visuell markering av Builder-förslag
- exakt terminologi för `Specialkost` kontra `Specialanpassningar`
- hur planeringen redigeras efter bekräftelse
- hur status `Klar/Producerat` bäst hanteras på grupp- respektive portionsnivå
- hur tillägg presenteras för olika kunder
- hur dynamiska måltidsalternativ 0..n presenteras
- framtida texturmetadata i Builder
- exakt modell för publicerad meny och operational override i UI

---

## 18. Dokumentets roll framåt

Detta är den levande produkt- och UX-specifikationen för Kommun Planera 2.0.

Vid varje kommande gate ska vi:

1. uppdatera detta dokument om ett produktbeslut ändras eller förtydligas
2. därefter instruera Copilot att implementera endast den godkända gaten
3. validera UI/UX och dataflöde
4. först därefter gå vidare

På så sätt förblir implementationen underställd den verkliga köksprocessen och inte tvärtom.
