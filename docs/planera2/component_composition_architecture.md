📄 Component Composition Architecture – Planera 2.0
🎯 Syfte

Detta dokument definierar hur flera komponenter (component_id) sätts samman till en serveringsbar enhet i Yuplan.

Målet är att:

Möjliggöra återanvändbara måltider
Behålla komponenter som systemets kärna
Skapa en stabil grund för menybyggare, event, recept och inköp
Undvika att logik sprids i fel lager
🧠 Kärninsikt

En komponent är en byggsten.
En composition är en sammansättning av byggstenar.

👉 Systemet ska aldrig tänka:

“en rätt = en sak”

👉 Systemet ska tänka:

“en servering = flera komponenter”

🧱 Definition
Composition

En composition är en återanvändbar sammansättning av komponenter som tillsammans utgör en servering.

Exempel:

Köttbullar + potatismos + gräddsås
Pytt i panna + rödbetor + ägg
Gulaschsoppa + bröd
Caesar-sallad + kyckling + bacon
🔑 Grundprinciper (MÅSTE följas)
1. Component är alltid sanningen
Alla kopplingar går via component_id
Composition innehåller endast referenser

👉 Ingen logik eller data dupliceras

2. Composition är återanvändbar
Ska kunna sparas i ett måltidsbibliotek
Ska kunna användas i flera menyer
Ska kunna återanvändas i olika kontexter
3. Composition är oberoende av antal
Innehåller inga portionsberäkningar
Innehåller inga volymer
Innehåller ingen produktion

👉 Den beskriver vad som serveras, inte hur mycket

4. Composition innehåller ingen beräkningslogik
Ingen koppling till Planera engine
Ingen specialkostlogik
Ingen kostnadslogik

👉 Endast struktur

🧱 Datamodell (minimal v1)
Composition
composition:
  composition_id (PK)
  canonical_name
  description (optional)
  course_type (optional)
  is_active
  created_at
  updated_at
CompositionItem
composition_item:
  composition_item_id (PK)
  composition_id (FK)
  component_id (FK)
  role
  sort_order
🎭 Role (kritisk del)

Varje komponent i en composition måste ha en roll.

Exempel:

main
side
sauce
garnish
bread
beverage
accompaniment
add_on
Viktigt

Role ska:

vara flexibel
inte hårdkodas globalt
kunna utökas över tid
🧠 Exempel
Köttbullar med mos
composition: meatballs_plate

items:
  - component_id: meatballs
    role: main

  - component_id: mashed_potato
    role: side

  - component_id: cream_sauce
    role: sauce
Gulaschsoppa med bröd
composition: goulash_meal

items:
  - component_id: goulash_soup
    role: main

  - component_id: bread
    role: bread
🔄 Utbyte av komponenter

Systemet måste tillåta att en komponent byts ut utan att hela composition bryts.

Exempel:

original:
  sauce: cream_sauce

updated:
  sauce: brown_sauce

👉 Detta ska inte skapa en helt ny logik
👉 Endast en variant eller ny composition

🍽 Course Type (valfri, lätt)

Composition kan ha en lätt klassificering:

Exempel:

main_course
dessert
starter
beverage_set

👉 Detta är endast metadata, inte logik

🧾 Vad räknas som composition?
✔️ Ja
Caesar-sallad
Köttbullar med mos
Soppa med bröd
Dagens lunch
❌ Nej
En enskild komponent (det är component)
En menyvecka
Ett event
En produktionslista
🥤 Dryck & tillbehör

Dryck och tillbehör ska:

vara egna komponenter
kunna ingå i composition
möjliggöra kostnadsberäkning senare

Exempel:

- component_id: ramlosa
  role: beverage
🔗 Koppling till övriga system
Meny
MenuDetail → Composition → Components
Planera 2.0
Engine bryr sig inte om composition direkt
Composition används via adapters
Event / Bankett
Event → Course → Composition → Components
Recept
Component → Recipe

👉 Recept kopplas aldrig till composition

⚠️ Viktiga designfällor
❌ 1. Lagra måltid som text
"köttbullar med mos"

→ går inte att skala

❌ 2. Koppla recept till composition

→ bryter återanvändbarhet

❌ 3. Lägga logik i composition

→ förstör separationen mot engine

🚀 Framtida möjligheter

Med denna struktur kan Yuplan senare:

koppla recept till komponenter
räkna ingredienser
generera inköpslistor
göra kostnadsberäkningar
optimera produktion
ge AI-förslag
🧠 Strategisk betydelse

Composition-lagret är:

👉 Bron mellan:

komponent (lego)
meny
planering
event

Utan detta lager:

→ menybyggaren blir instabil
→ komponenttänket bryts
→ systemet blir svårt att skala

✅ Sammanfattning
Component = byggsten
Composition = sammansättning
Role = funktion i serveringen

👉 Allt kopplas via component_id
👉 Ingen logik i composition
👉 Full återanvändbarhet