📄 Ingredient / Purchasing Architecture – Planera 2.0
🎯 Syfte

Detta dokument definierar hur Yuplan ska hantera ingredienser, kostnad och framtida inköpskopplingar som ett eget lager ovanpå komponent- och receptmodellen.

Målet är att:

skilja tydligt mellan component och ingredient
möjliggöra kostnadsberäkning tidigt
stödja fria men strukturerade ingrediensrader i v1
förbereda för framtida inköpskoppling utan ombyggnad
🧠 Kärnprincip

Component är det som serveras eller produceras
Ingredient är det som används eller köps in

Exempel:

oxfile = component
oxfilé hel, oxfilé putsad, salt, smör = ingredients
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
   ↓
(optional later) Purchasing references
🔑 Grundprinciper
1. Ingredient är inte samma sak som Component

Component beskriver:

det som planeras eller serveras
det som kan återanvändas i compositions
det som bär portionsmål, svinn och receptkoppling

Ingredient beskriver:

det som används i ett recept
det som kan summeras till inköp
det som kan bära pris och leverantörskoppling senare
2. V1 utgår från fria men strukturerade ingrediensrader

I första versionen ska en ingrediensrad vara fri, men inte ostrukturerad.

Varje rad ska innehålla:

ingrediensnamn
mängd
enhet
ev. pris
ev. anteckning

Detta gör att systemet kan börja stödja:

kostnadsberäkning
enklare summering
receptimport
framtida standardisering
3. Systemet ska vara förberett för framtida ingredient-objekt

Även om v1 börjar med fria ingrediensrader, ska modellen byggas så att en ingrediensrad senare kan kopplas till ett mer stabilt ingredient-/purchasing-objekt.

Det innebär:

inga låsningar till fri text som enda sanning
möjlighet att senare binda ingrediensrader till riktiga inköpsartiklar
4. Flera leverantörer per ingrediens måste stödjas senare

Samma råvara kan finnas som flera inköpsalternativ.

Exempel:

oxfilé hel
oxfilé färdigstyckad
olika grossister
olika prisnivåer
olika svinn

Systemet måste därför senare kunna stödja:

flera möjliga purchasing references per ingredient
olika kostnadsutfall beroende på val
🧱 Datamodell (v1)
RecipeIngredientLine
recipe_ingredient_line:
  recipe_ingredient_line_id
  recipe_id

  ingredient_name
  quantity_value
  quantity_unit

  unit_price_value      // optional
  unit_price_unit       // optional
  note                  // optional

  sort_order
🧾 Exempel
ingredient_name: potatis
quantity_value: 900
quantity_unit: g

ingredient_name: grädde
quantity_value: 4
quantity_unit: dl

ingredient_name: salt
quantity_value: 10
quantity_unit: g
⚖️ Enhetsstrategi
V1

Systemet ska kräva:

numeriskt värde
vald enhet

Tillåt exempelvis:

g
kg
ml
cl
dl
l
st
Viktig princip

Mängd utan enhet får inte förekomma.

Exempel:

❌ 120
✔ 120 g
✔ 4 cl
✔ 2 st

Detta är viktigt för att möjliggöra:

totalsummering
receptskalning
kostnad
framtida konvertering
Långsiktig riktning
vikt blir huvudspår för kalkyl och inköp
volym tillåts som input
senare kan ingrediensspecifika konverteringar läggas till
💰 Prisstrategi (v1)
Tidig modell

I v1 ska pris kunna sättas direkt på ingrediensraden.

Detta gör att systemet tidigt kan stödja:

ungefärlig kostnadsbild
portionskostnad
receptkostnad

Exempel:

potatis
900 g
pris: 18 kr / kg
Senare modell

Senare ska pris och leverantörsinformation kunna flyttas till ett separat ingredient-/purchasing-lager.

Det innebär att v1 ska vara byggd så att detta går att lägga till utan att recept bryts.

🧱 Framtida lager: Ingredient Catalog

Senare kan Yuplan få ett eget ingredient-lager med t.ex.:

ingredient:
  ingredient_id
  canonical_name
  default_uom
  tags
  is_active

Detta ska dock inte vara krav i v1.

🧱 Framtida lager: Purchasing References

Senare ska en ingrediens kunna kopplas till flera inköpsalternativ.

Exempel:

ingredient_purchase_option:
  purchase_option_id
  ingredient_id
  supplier_name
  supplier_sku
  pack_size
  price_value
  price_unit
  waste_percent
  is_active
🧠 Viktig designprincip

Systemet ska inte anta att en ingrediens har exakt ett “rätt” inköpsobjekt.

Det måste stödja:

flera grossister
flera kvaliteter
flera artikeltyper
olika svinn
🔄 Kalkylkedja

Den långsiktiga kalkylkedjan ser ut så här:

Component
   ↓
Default Recipe
   ↓
Ingredient Lines
   ↓
Quantity + Unit
   ↓
(optional) Price / Purchasing Option
   ↓
Recipe Cost
   ↓
Cost per Component / Portion
🧠 Default-sanning

Detta ska gälla:

component = stabil identitet
recipe = metod för att producera komponenten
ingredient line = vad receptet består av
price = temporär eller framtida inköpsrelaterad kostnadsdata
AI/import = endast förslag, aldrig automatisk sanning
🤖 Import och framtid

Detta lager ska stödja framtida receptimport.

Vid import ska systemet försöka tolka:

ingrediensnamn
mängd
enhet
ev. prisinformation

Men i v1 är det okej att detta fortfarande blir:

fria men strukturerade ingrediensrader
⚠️ Viktiga designfällor
❌ 1. Göra ingredient = component

Fel, eftersom det blandar serveringslogik med inköpslogik.

❌ 2. Tillåta mängd utan enhet

Förstör framtida kalkyl och summering.

❌ 3. Tvinga in grossistkoppling för tidigt

Ger onödig komplexitet och blockerar användning.

❌ 4. Låsa en ingrediens till en enda leverantör

Passar inte verkligheten.

🚀 Vad detta möjliggör

När detta lager finns kan Yuplan senare stödja:

receptkostnad
portionskostnad
food cost
inköpssummering
flera leverantörer
val mellan inköpsalternativ
AI-stöd för kostnad och optimering
✅ Sammanfattning
Ingredient är inte samma sak som Component
V1 bygger på fria men strukturerade ingrediensrader
Mängd + enhet är obligatoriskt
Pris kan sättas direkt på ingrediensraden i början
Senare ska ingredients kunna kopplas till katalog och purchasing options
Flera leverantörer och inköpsalternativ måste stödjas
Modellen ska vara förberedd för framtid, utan att bli tung för tidigt