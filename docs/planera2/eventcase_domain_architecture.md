🎯 Syfte

Detta dokument beskriver hur Yuplan i framtiden ska stödja hotell-, bankett- och storköksverksamhet som en domän ovanpå Planera 2.0.

Målet är att:

Möjliggöra planering av större event och produktionstillfällen
Stödja hela flödet från meny till inköp och kalkyl
Undvika att bygga ett separat system
Säkerställa att Planera 2.0 förblir en generell motor
🧠 Kärnprincip

Planera 2.0 är motorn
EventCase är en domän ovanpå motorn

Detta innebär:

Ingen separat “bankettmotor”
Samma kärna används för alla typer av kök
Domänlogik byggs som lager ovanpå
🔄 Skifte i planeringsmodell
Kommun / traditionell modell

Planering sker utifrån:

vecka
dag
måltid
avdelning
antal personer
specialkost
Event / bankettmodell

Planering sker utifrån:

event / case
kund / grupp
datum / servicepunkter
antal gäster
meny (flera rätter)
produktion och råvaror
kostnad och prissättning

👉 Planeringsobjektet förändras från vecka → event

🧱 Kärnobjekt: EventCase

Ett EventCase representerar ett uppdrag eller arrangemang.

Exempel på attribut:
titel / namn
datum
plats / venue
kund / grupp
antal gäster
serveringsform
status
anteckningar
Exempel:
Datum: 2026-05-19
Grupp: Företagsbankett
Gäster: 1300
Format: 3-rätters middag
Typ: plated dinner
🧩 Struktur: Event → Segment → Course → Item
1. Event

Själva caset (ramen)

2. Segment

Uppdelning av gäster

Exempel:

standard
vegetarisk
vegansk
allergi
VIP
barn
personal

Varje segment har:

antal gäster
ev. egen menyvariation
3. Course

Serveringssteg

Exempel:

starter
main
dessert
late supper
coffee
4. Item

Faktiska komponenter

Exempel:

protein
sås
garnityr
dekoration

👉 Här kopplas till component_id

🔗 Koppling till komponentmodellen

Varje item bör peka på:

component_id

Detta möjliggör:

återanvändning
receptkoppling
allergenhantering
inköpsberäkning
statistik

👉 Component är fortfarande systemets nav

🍳 Recept- och ingredienslogik

EventCase ska inte innehålla fri text för mängder.

Istället:

Component → Recipe
Recipe → Ingredients
Ingredients → mängd + enhet
Exempel:
3 g gräslök per portion
1300 gäster
→ 3900 g totalt
🧾 Produktionsoutput

Systemet ska kunna generera:

1. Produktionslista
antal portioner per segment
antal per variant
2. Ingredienssammanställning
total mängd per råvara
3. Beställningslista
inköpsanpassad vy
4. Kalkyl
total kostnad
kostnad per person
marginal
prisförslag
🖼 Assets & dokumentation

EventCase ska kunna bära:

bilder (provläggning)
PDF:er
anteckningar
körscheman

Koppling kan ske till:

event
course
item
💰 Kalkylkedja (framtida)
ingredienspris
receptkostnad
portionskostnad
total eventkostnad
kostnad per kuvert
marginal
försäljningspris
🧠 Arkitekturprincip

Detta ska:

✔ ligga ovanpå Planera 2.0
✔ använda samma motor
✔ använda komponentmodellen
✔ använda adapters

Detta ska INTE:

❌ påverka core engine
❌ introducera speciallogik i kärnan
❌ skapa parallell arkitektur

🧩 Relation till Planera 2.0

Planera 2.0 ska arbeta med:

demand
categories
quantities
production output

EventCase-domänen:

organiserar input
strukturerar komponenter
kopplar till recept
visualiserar output
🔮 Strategisk betydelse

Denna domän möjliggör:

hotell
bankett
catering
konferens
storkök
restaurang med gruppbokningar

👉 Samma motor, fler användningsområden

⚠️ Viktig avgränsning

Detta dokument beskriver:

✔ framtida domän
✔ arkitektur
✔ riktning

Detta dokument beskriver inte:

❌ implementation
❌ databasdesign i detalj
❌ UI
❌ prioriterad roadmap

✅ Sammanfattning

Planera 2.0 ska:

vara generisk
vara komponentbaserad
kunna bära flera domäner

EventCase visar varför detta är nödvändigt.

👉 Veckoplanering och eventplanering är olika uttryck
👉 men samma underliggande problem

behov → produktion → resurser