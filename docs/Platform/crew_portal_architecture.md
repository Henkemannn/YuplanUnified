🧭 Layer definition

Layer: Input / Engagement
Depends on: Planera 2.0 Engine
Type: Future Lab – Platform Module

🎯 Syfte

Crew Portal är en framtida modul inom Yuplan som fungerar som:

informationsportal för användare (crew, personal, anhöriga m.fl.)
kommunikationskanal mellan kök och användare
strukturerad datakälla till Planera 2.0

Målet är att:

samla information i ett system
minska manuella processer
förbättra säkerhet och kommunikation
skapa ett kontinuerligt inflöde av strukturerad data till produktionsmotorn
🧠 Kärnprincip

Crew Portal är inte en UI-feature
Crew Portal är en datakälla till Planera 2.0

🏗 Plattformskontext

Yuplan byggs som en plattform med tydliga lager:

[ Crew Portal ]      → input / engagement
[ Kitchen Portal ]   → operativ vy
[ Admin Portal ]     → konfiguration

            ↓

[ Planera 2.0 Engine ] → compute layer
⚠️ Kritiska arkitekturregler
1. Ingen logik i portalen

Crew Portal får aldrig innehålla produktionslogik.

All beräkning sker i:

Planera 2.0 Engine
2. Portal = input, inte beräkning

Portalen:

samlar data
strukturerar data
skickar data

Portalen:

räknar inte
tolkar inte
beslutar inte
3. Adapter är enda kopplingen
Crew Portal → PortalSelectionAdapter → Planera 2.0 Engine

Ingen direktkoppling till motorn.

4. Systemet måste fungera utan portal

Om portalen inte används:

→ Planera 2.0 ska fungera ändå

Detta är ett krav.

🔧 Problem som löses (Offshore)

Nuvarande situation:

whiteboards (meny)
printade OBS-kort
laminerade listor
PDF/intranät
muntlig kommunikation
Konsekvenser
splittrad information
manuella processer
risk för fel (särskilt specialkost)
ineffektiv kommunikation
💡 Lösning

En mobilvänlig portal som samlar:

meny
specialkost
safety information
dokumentation
kommunikation
🧩 Funktionella moduler
1. Matsedel & kökskommunikation
veckomeny
lunch/middag-kontext
specialkostanmälan
allergiprofil per användare
köksmeddelanden

👉 Detta är direkt kopplat till Planera 2.0

2. Safety & OBS
safety bulletins
veckans OBS
kampanjer
drill-info
pushnotiser

👉 Driver användning, ej kopplat till motorn

3. Riggkarta
deck overview
muster stations
faciliteter

👉 Onboarding / orientering

4. Crew-information
kontaktlistor
rutiner
policy
dokument
5. Daglig information
nyheter
väder
helikopterinfo
aktiviteter
🔥 Strategiskt viktig funktion
Crew Profile

Varje användare kan ange:

allergier
specialkost
preferenser
🔄 Datapipeline
Crew → Portal → Adapter → Planera 2.0 → Produktion
🔌 Integration med Planera 2.0
Input från portalen
specialkost per person
(framtid) val per måltid
(framtid) närvaro (POB)
Adapter
PortalSelectionAdapter

Ansvar:

läsa portaldata
gruppera per kategori
skicka till motorn
Output (exempel)
{
  "breakdown": [
    {"category": "crew_day", "quantity": 86},
    {"category": "crew_night", "quantity": 42},
    {"category": "special", "quantity": 9}
  ]
}
🔄 Skillnad mot Planera 1.0
Planera 1.0	Planera 2.0
UI-styrd	Motor-styrd
Manuell input	Portal + adapters
Normal/Special	Category-based
Kommunfokus	Multi-domain
💰 Affärsvärde
För köket
automatiserad specialkost
färre fel
bättre planering
För användare
enkel tillgång till info
mobilvänligt
För organisationen
minskat pappersarbete
central kommunikationskanal
📈 Kommersiell potential

Typisk prissättning:

8 000 – 12 000 kr / månad / rigg

Motivering:

låg kostnad i kontext
hög operativ nytta
ersätter manuella processer
🔄 Skalbarhet

Crew Portal kan återanvändas för:

äldreboenden (anhörigportal)
skolor (föräldraportal)
sjukhus
hotell
restaurang
🚀 Framtida expansion
POB-integration
helikoptermanifest
dokumentportal
pushnotiser
val per måltid
beteendedata
🧠 Strategisk insikt

Crew Portal är inte en feature
Det är en dataproducent

Detta innebär:

Planera 2.0 blir starkare
Yuplan får datadrivet försprång
systemet går från verktyg → plattform
⚠️ Viktig avgränsning

Detta dokument beskriver:

✔ arkitektur
✔ riktning
✔ roll i plattformen

Det beskriver inte:

❌ implementation
❌ UI-detaljer
❌ prioriterad roadmap

✅ Sammanfattning

Crew Portal:

löser ett konkret problem
fungerar som input-layer
kopplas via adapters
påverkar inte motorns logik
stärker Yuplan som plattform