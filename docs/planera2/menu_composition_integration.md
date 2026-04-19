📄 Menu → Composition Integration – Planera 2.0
🎯 Syfte

Detta dokument beskriver hur menyer i Yuplan ska byggas med hjälp av compositions istället för fri text.

Målet är att:

Eliminera ostrukturerad menydata
Säkerställa att all planering bygger på komponenter
Möjliggöra menybyggare med drag & drop (“lego-principen”)
Skapa en stabil grund för recept, inköp, kostnad och AI
🧠 Kärninsikt

En meny beskriver inte vad som skrivs.
En meny beskriver vad som serveras.

👉 Därför:

Menyrader ska peka på compositions, inte text

🔗 Grundstruktur
MenuDetail
   ↓
Composition
   ↓
Component[]

🏗️ Ägarskap mellan lager (cleanup 2026-04)

- Builder = Library Layer
  - Äger endast biblioteket: components, compositions, alias-stöd och bibliotek-import.
  - Ska inte äga menykontext (day/meal-slot, unresolved-listor, meny-kostnadsöversikt).

- Menu-context module = Menu Context Layer
  - Äger menyflöden: skapa meny, import av menyrader, resolve/unresolved och meny-orienterad kostnadsöversikt.
  - Får återanvända Builder-biblioteket, men inte flytta tillbaka ägarskap till Builder.

- Production = separat lager
  - Produktions-/körlogik hålls utanför både Builder och Menu Context.
  - Integration sker via tydliga gränser, inte via blandade ansvar i samma modul.

🔑 Grundprinciper
1. Menyrad = en Composition

Varje rad i menyn representerar exakt en composition.

menu_detail → composition_id

👉 Ingen blandning
👉 Ingen multipel struktur i samma rad

2. Composition är sanningen – text är visning
❌ "Köttbullar med mos"
✔ composition_id = meatballs_plate

Text används endast för:

visning
utskrift
UI
3. Composition består av komponenter
composition:
  - meatballs
  - mashed_potato
  - cream_sauce

👉 Alla delar är komponenter
👉 Inget är “inbakat” i en komponent

4. Ingen logik i meny-lagret

Menyn:

räknar inget
innehåller inga mängder
innehåller ingen specialkostlogik

👉 Den pekar endast på struktur

🧱 Datamodell
Menu
menu:
  menu_id
  site_id
  week_key
  version
  status
MenuDetail
menu_detail:
  menu_detail_id
  menu_id

  day
  meal_slot

  composition_ref_type   // composition | unresolved
  composition_id         // nullable
  unresolved_text        // nullable

  note
  sort_order
🔐 Kritisk designregel

Varje menyrad måste vara:

1) resolved:
   composition_id = X

ELLER

2) unresolved:
   unresolved_text = "köttbullar m potatis"

👉 ALDRIG fri text utan struktur

🔄 Importflöde

Importerade menyer är alltid text.

Exempel:

“Köttbullar med potatis”
“Köttbullar & mos”
“Gulasch med bröd”
resolve_composition(text)
norm = normalize(text)

IF alias exists:
  return composition_id

IF fuzzy match high confidence:
  return composition_id + skapa alias

ELSE:
  return unresolved
🧾 Alias-tabell
composition_alias:
  alias_text
  alias_norm
  composition_id
  confidence
🧠 Viktig princip

Systemet får aldrig gissa fel.

👉 Vid osäkerhet:

→ unresolved
🔧 Förädling av meny (efter import)

Systemet ska stödja:

Lista unresolved
GET unresolved menu rows
Koppla till composition
bind(menu_detail_id, composition_id)
Skapa alias

När en rad binds:

alias skapas automatiskt
🧠 Menybyggaren (framtida UI)
Vänster
Composition library
Filter (kategori, tags)
Mitten
Veckovy (drag & drop)
Höger
Components i vald composition
🧱 Lego-principen

Användaren bygger menyer genom att använda compositions.

Exempel
Oxfilé / Sparris / Rödvinssås / Potatispuré

Senare:

Byt:
Potatispuré → Potatisgratäng

👉 Ingen ny rätt behöver byggas från grunden
👉 Bara en komponent byts ut

🔗 Koppling till framtida funktioner
Recept
Component → Recipe
Inköp
Component → Ingredient → Order
Kostnad
Component → price → total cost
Planera 2.0 Engine
Menu → Composition → (via adapter) → Engine
⚠️ Viktiga designfällor
❌ 1. Meny som text

→ ingen struktur
→ ingen skalbarhet

❌ 2. Composition som komponent

→ leder till explosion av komponenter

❌ 3. Koppla logik till meny

→ bryter arkitektur

🧠 Designprincip (kritisk)

Yuplan ska:

erbjuda struktur
möjliggöra flexibilitet

Yuplan ska INTE:

låsa arbetssätt
bestämma antal alternativ
bestämma menystruktur
🧩 Flexibilitet

Systemet ska stödja:

flera lunchalternativ
flera compositions per dag
olika upplägg per kund
olika domäner (kommun, hotell, offshore, bankett)
🚀 Framtida möjligheter

Med denna modell kan Yuplan:

bygga menybuilder (drag & drop)
stödja AI-förslag
återanvända rätter över år
koppla till recept
skapa inköpslistor
räkna kostnad per måltid
🧠 Strategisk betydelse

Detta lager:

👉 kopplar ihop

meny
composition
component
planering

👉 och möjliggör hela Yuplan-plattformen

✅ Sammanfattning
Menyrad = en composition
Composition = flera komponenter
Component = minsta byggstenen

👉 Allt bygger på component_id
👉 Allt går via composition
👉 Ingen fri text som sanning