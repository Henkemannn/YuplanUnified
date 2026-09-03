# Yuplan Home — Future Lab

**Status:** Future Lab / idéspår  
**Prioritet nu:** Ska inte implementeras ännu  
**Plattformsprincip:** Yuplan Home ska byggas ovanpå samma generiska kärna som Yuplan Professional, inte som ett separat system.

## Sammanfattning

Yuplan Home är ett framtida konsumentspår för hushållens måltidsplanering, recept, inköp och minskat matsvinn.

Grundflödet är:

**Vad ska vi äta? → Planera veckan → Beräkna portionsbehov → Recept → Ingredienser → Inköp**

Samma grundarkitektur som används professionellt ska återanvändas i hemmet:

**Components → Dishes / Compositions → Recipes → Planned Menu → Ingredient/Purchasing Layer → Order Adapters**

Home blir huvudsakligen en konsumentanpassad application layer och frontend ovanpå Yuplans gemensamma plattform.

---

## Grundidé

Användaren bygger sin kommande vecka genom drag & drop från sitt personliga bibliotek av rätter.

Exempel:

- Måndag — Köttbullar, potatismos, gräddsås
- Tisdag — Lax, potatis, kall sås
- Onsdag — Tacos
- Torsdag — Pasta Bolognese
- Fredag — Pizza

Bakom varje rätt finns strukturerade recept och ingredienser enligt samma grundtänk som Menu Builder.

Det viktiga är att veckoplaneringen inte bara blir text eller receptlänkar. Varje vald rätt ska vara en strukturerad Dish/Composition som Yuplan kan räkna vidare på.

---

## Automatisk inköpslista

När veckan är planerad räknar Yuplan automatiskt ut vad hushållet behöver köpa utifrån:

- valda rätter
- antal personer
- recept
- ingrediensmängder
- portionsskalning

Resultatet blir en komplett inköpslista för veckan.

Nästa steg är integration mot exempelvis:

- ICA
- Coop
- Willys
- Oda
- Mathem

Yuplan kan då översätta ingrediensbehov till verkliga produkter och skapa en färdig varukorg för:

- hemleverans
- pickup
- överföring till butikens egen app eller shoppinglista

Detta följer principiellt samma adapterarkitektur som Yuplan senare kan använda professionellt mot grossister och andra leverantörer.

---

## Minskat matsvinn

Yuplan Home kan utvecklas med ett enkelt hushållslager:

> Vad har vi redan hemma?

Systemet kan då:

- dra av befintliga råvaror från inköpslistan
- föreslå rätter baserat på vad som finns hemma
- använda rester och öppnade förpackningar
- optimera veckomenyn för mindre svinn

Målet blir inte bara måltidsplanering utan smartare hushållsekonomi och mindre matsvinn.

På sikt kan detta även utvecklas med bäst-före-datum, ungefärliga lagersaldon och förpackningsstorlekar, men sådan komplexitet ska inte byggas in i kärnan i förtid.

---

## Community och sharing

Yuplan Home kan senare kopplas till Yuplans framtida community-/sharingmodell.

Användare kan exempelvis:

- dela egna rätter och recept
- spara andras rätter till sitt bibliotek
- skapa egna versioner/forks
- dela hela veckomenyer
- följa skapare
- betygsätta recept

### Viktig ägarprincip

Originalet ska alltid behållas separat.

När någon sparar eller ändrar en delad rätt ska användaren få en egen version i sitt bibliotek. En användares ändring får inte mutera originalet hos skaparen.

Detta bör passa samma långsiktiga modell som övriga Yuplan-bibliotek: stabil identitet, versionering och tydlig ownership.

---

## AI ovanpå strukturerad data

AI ska användas ovanpå Yuplans strukturerade data, inte ersätta den.

Exempel på instruktion:

> Vi är två vuxna och två barn. Fisk två gånger, vegetariskt en gång, max 30 minuters matlagning och budget 1 300 kr.

Yuplan kan skapa ett veckoförslag som fortfarande består av riktiga strukturerade Dishes + Recipes.

Användaren kan sedan säga:

- Byt torsdag mot något med kycklingen vi har hemma.
- Gör veckan 200 kr billigare.
- Vi får fyra gäster på lördag.

Yuplan räknar därefter om recept, portionsbehov och inköp.

AI-lagret ska alltså välja, kombinera och föreslå över canonical data. Det ska inte skapa ett separat parallellt sanningslager av fri text.

---

## Plattformstänk

Yuplan Home ska **inte** byggas som ett separat system.

### Målbild

**Yuplan Core**

- Components
- Dishes / Compositions
- Recipes
- Menus
- Planning Engine
- Ingredient / Purchasing Layer
- Sharing
- AI
- Order Adapters

**Application Layers**

- Kommun
- Offshore
- Hotel / Banquet
- Yuplan Home

Home blir alltså huvudsakligen en ny konsumentanpassad frontend och Home-specifika adapters ovanpå samma kärnplattform.

---

## Affärsmöjlighet

Yuplan Home öppnar flera möjliga affärsmodeller:

1. **B2C** — gratisversion + Premium-abonnemang.
2. **Transaktions-/affiliateintäkter** från matbeställningar.
3. **Partnerskap med dagligvaruhandel.**
4. **White-label / B2B2C** — exempelvis "Veckoplanering powered by Yuplan" direkt i en butikskedjas ekosystem.

Den större strategiska möjligheten är att Yuplan inte bara hjälper användaren att hitta recept, utan ligger i hela kedjan:

**Vad ska vi äta? → Planera veckan → Beräkna mängder → Matcha produkter → Skapa varukorg → Genomför köp**

---

## Strategisk potential

Yuplan Home är intressant eftersom det inte kräver en helt ny produktmotor om Yuplans kärna byggs rätt.

Samma strukturella problem återkommer i alla Yuplan-spår:

- vilka måltider ska produceras eller ätas?
- för hur många?
- vilka recipes/components krävs?
- vilka råvarumängder följer av det?
- vad finns redan tillgängligt?
- vad behöver köpas?
- hur översätts ett abstrakt ingrediensbehov till verkliga produkter/leverantörer?

Skillnaden ligger framför allt i business context och frontend.

Det gör Home strategiskt värdefullt även innan produkten byggs: idén fungerar som ett framtida test på att kärnarkitekturen verkligen är generell.

---

## Viktigt för nuvarande utveckling

Yuplan Home ska sparas som Future Lab-spår och **inte börja byggas nu**.

Nuvarande prioritet är fortfarande att stabilisera Yuplans kärna och Professional-produkten.

Det viktiga redan nu är däremot att följande områden inte låses till Kommun/Offshore-specifika antaganden:

- Components
- Dishes / Compositions
- Recipes
- Menus
- portionsskalning
- ingredient aggregation
- sharing / version ownership
- order adapters
- produkt-/leverantörsmatchning

Home ska senare kunna konsumera samma kontrakt utan att Professional behöver byggas om.

---

## Arkitekturlås för framtida utveckling

När relevanta delar av kärnan byggs bör följande principer hållas öppna:

1. **Recipe och ingredient-data ska vara generisk.** Inte bunden till kommun, offshore eller grossist.
2. **Portionsskalning ska vara en kärnförmåga.** Hushåll och storkök skiljer sig i skala, inte i grundproblemet.
3. **Ingredient requirement ska vara separat från product selection.** Exempel: "1,2 kg potatis" är behovet; ICA:s specifika potatisförpackning är en adapter-/produktmatchningsfråga.
4. **Order adapters ska vara leverantörsspecifika ytterkanter.** Kärnan ska inte känna ICA, Coop, grossister etc.
5. **Sharing ska använda copy/fork/version semantics.** Delat innehåll får inte skapa otydligt ägarskap.
6. **AI ska konsumera canonical data.** AI får inte bli ett separat system för recept, menyer eller inköpslogik.
7. **Home-inventory ska vara ett senare lager.** Det får inte göra dagens Professional-kärna onödigt komplex.

---

## Möjliga framtida utvecklingsfaser

Detta är endast en tänkbar framtida ordning, inte aktiv backlog.

### Home 0 — personlig veckoplanering

- personligt Dish/Recipe-bibliotek
- drag & drop-vecka
- hushållsstorlek
- portionsskalning
- genererad inköpslista

### Home 1 — smart inköpslista

- kategorisering
- summering/deduplikering av ingredienser
- förpackningsstorlekar
- manuellt "har hemma"

### Home 2 — retailer adapter

- ingredient → retailer product matching
- färdig varukorg
- pickup / delivery / shopping list

### Home 3 — waste intelligence

- hushållslager
- rester
- öppnade förpackningar
- förslag utifrån befintligt lager

### Home 4 — community

- publishing
- sharing
- forks
- creators
- ratings
- delade veckomenyer

### Home 5 — AI planner

- constraints
- budget
- nutrition/preferences där relevant
- intelligent menu substitution
- automatiska omräkningar

---

## Risker och frågor att lösa senare

Idén är stark, men några delar blir egna svåra problem och ska behandlas som adapters/lager snarare än smygas in i kärnan:

- produktmatchning mellan generisk ingrediens och butikens SKU
- förpackningsstorlek kontra exakt receptbehov
- prisdata och prisförändringar
- tillgänglighet per butik
- retailer-API:er och kommersiella avtal
- substitutionsprodukter
- lagerdata i hemmet och hur mycket användaren faktiskt orkar registrera
- recipe/community moderation och ownership

Ingen av dessa blockerar grundidén.

---

## Långsiktig strategisk målbild

Yuplan ska kunna bli en generell plattform för:

**idé om måltid → planering → portionsbehov → recept → ingredienser → inköp**

samma kärna oavsett om användaren är:

- ett äldreboende
- en offshoreplattform
- ett hotell eller bankettkök
- ett hushåll

Det är den viktigaste arkitekturella lärdomen från Yuplan Home-idén redan idag.
