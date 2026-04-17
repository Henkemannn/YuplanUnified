📄 Component Recipe Architecture – Planera 2.0
🎯 Syfte

Detta dokument definierar hur recept ska kopplas till komponenter i Yuplan.

Målet är att:

ge varje komponent ett eller flera recept
möjliggöra kalkyl, produktion och framtida inköp
stödja återanvändning över menyer och år
förbereda för tidig receptimport från befintliga underlag
🧠 Kärnprincip

Recept hör till komponent
inte till composition
och aldrig direkt till menytext

🔗 Grundstruktur
Menu
   ↓
Composition
   ↓
Component
   ↓
Recipe
   ↓
Ingredient lines
🔑 Grundprinciper
1. Component är navet

Varje recept kopplas till:

component_id

Det innebär att samma komponent kan användas i flera compositions, menyer och event men fortfarande bära sina recept på ett stabilt sätt.

2. Flera recept per komponent är tillåtet

Samma komponent kan ha flera olika recept.

Exempel:

Potatisgratäng
Anders potatisgratäng
Vegansk potatisgratäng

Detta är viktigt eftersom olika arbetsplatser och användare ofta har olika recept för samma komponent.

3. Ett recept kan vara default

För varje komponent ska ett recept kunna markeras som:

default_recipe = true

Detta recept används som utgångspunkt för:

kalkyl
framtida beräkningar
standardvisning

Om användaren försöker sätta ett nytt default-recept ska systemet ge en tydlig varning om att beräkningar och kalkyler kommer att utgå från detta recept.

4. Komponenten bär stabil produktionsmetadata

Detta ska ligga på komponentnivå, inte på receptnivå:

portionsvikt / målportion
svinnprocent
ev. standarddata för produktion

Exempel:

Oxfilé: 150 g råvikt per portion
Svinn: 7 %

Receptet ska tydligt visa vad det arbetar mot, men komponenten är den stabila sanningen.

🧱 Datamodell (minimal v1)
Component
component:
  component_id
  canonical_name
  default_uom
  target_portion_weight
  waste_percent
  is_active
Recipe
recipe:
  recipe_id
  component_id
  recipe_name
  visibility        // private | site | tenant
  is_default
  yield_portions
  notes
  created_at
  updated_at
RecipeIngredientLine
recipe_ingredient_line:
  recipe_ingredient_line_id
  recipe_id

  ingredient_name
  quantity_value
  quantity_unit

  optional_note
  sort_order
🧾 Visibility

Recept ska kunna ha olika synlighet:

private → endast för användaren
site → synligt på arbetsplatsen
tenant → synligt i hela organisationen

Detta gör att systemet kan stödja både personliga recept och gemensamma standardrecept.

⚠️ Viktig princip

Yuplan ska inte försöka avgöra vilket recept som är “rätt”.

Det är användaren eller kunden som ansvarar för att:

välja default-recept
avgöra vilket recept som ska användas i kalkyl
hålla sina recept relevanta

Systemet ska ge struktur och stöd, inte ta över verksamhetsansvaret.

🧂 Ingrediensrader (v1)
Grundregel

Varje ingrediensrad måste innehålla:

numerisk mängd
vald enhet

Exempel:

900 g potatis
4 dl grädde
10 g salt
2 st ägg
Varför detta är viktigt

Detta gör att systemet tidigt kan stödja:

enklare totalsummering
tidig kostnadsbild
framtida inköp
framtida receptskalning
Enheter (v1)

Tillåt i början t.ex.:

g
kg
ml
cl
dl
l
st

Systemet behöver inte kunna fullständig smart omvandling från dag 1, men det måste vara förberett för det genom att mängd och enhet alltid lagras strukturerat.

⚖️ Enhetsstrategi
V1
användaren måste ange mängd + enhet
systemet lagrar detta strukturerat
vissa enkla omvandlingar kan komma senare
Senare
stöd för ingrediensspecifika omvandlingar
vikt ↔ volym där det är rimligt
inköpsanpassning
🍽 Vikt kontra volym

Långsiktigt ska vikt vara huvudspår för:

kalkyl
inköp
produktion

Men systemet måste samtidigt stödja att många recept i verkligheten skrivs i:

dl
cl
l
st

Därför ska volym tillåtas som input från början.

🔄 Receptimport (tidig prioritet)

Receptimport ska prioriteras tidigt.

Målet är att användare ska kunna få in sina gamla recept i systemet utan att skriva om allt manuellt.

Importnivåer
1. Textimport

Användaren klistrar in ett recept i textform.

Systemet försöker tolka:

ingrediensrader
mängd
enhet
metod
2. Dokumentimport

Import från exempelvis PDF eller andra digitala underlag.

3. Bildimport / handskrivna recept

AI kan på sikt användas för att tolka:

handskrivna recept
bilder
foton av gamla pärmar

Detta ska dock ses som:

AI-assisted import

inte som automatisk sanning.

Användaren måste alltid kunna:

granska
justera
godkänna
🤖 AI-princip för receptimport

AI får gärna hjälpa till med:

tolkning
strukturering
förslag

AI får inte ensam avgöra slutresultatet.

Det rätta flödet är:

import → AI-förslag → användargranskning → sparat recept
🔧 Vad receptlagret möjliggör senare

När detta lager finns kan Yuplan senare stödja:

receptskalning
ingredienssummering
inköpsunderlag
kostnadsberäkning
food cost
prep-logik
frysplock
AI-förslag
⚠️ Viktiga designfällor
❌ 1. Koppla recept till composition

Fel, eftersom composition bara är en sammansättning.

❌ 2. Låta ingredienser vara fri text utan mängd/enhet

Då blir senare kalkyl och import mycket svårare.

❌ 3. Tvinga fram ett enda recept per komponent

Det passar inte verkligheten.

❌ 4. Låta AI importera utan granskning

För riskabelt.

✅ Sammanfattning
Recept hör till komponent
En komponent kan ha flera recept
Ett recept kan vara default
Komponenten bär portionsvikt och svinn
Recept bär ingredienser, yield och metod
Ingrediensrader ska vara strukturerade från början
Receptimport ska prioriteras tidigt
AI ska hjälpa, inte bestämma