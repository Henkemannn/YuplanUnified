🧭 Layer definition

Layer: Input / Operational UI
Depends on: Planera 1.0 (pilot), Planera 2.0 (future)
Type: Hybrid – Pilot + Future Lab

🎯 Syfte

Avdelningsportalen är en modul inom Yuplan som används av avdelningar för att:

göra menyval
kommunicera behov till köket
ge tydlig status på planering

Den ska:

vara extremt enkel att använda
fungera för personal med låg teknisk vana
ge tydlig status (klar/ej klar)
fungera som input till kökets planering
i framtiden fungera som input-layer till Planera 2.0
🧠 Kärnprincip

Portalen ska kännas enkel i UI
men vara strukturerad i data

🟢 Portal V1 – Pilotversion
🎯 Mål
fungera stabilt i pilot
vara visuellt tydlig
vara självinstruerande
minimera fel
🔐 Inloggning
användare loggar in
systemet vet vilken avdelning användaren tillhör
🏠 Startvy (Portal Home)
A. Välkomsttext

Kort instruktion:

"Välj vecka, gör dina val och tryck Klar."
B. Veckolista

Visar publicerade veckor.

Per vecka:

vecka + datumintervall
status
Statusmodell
Status	Betydelse
🟢 Klar	Avdelningen har tryckt “Klar”
🟡 Påbörjad	Några val gjorda
⚪ Ej påbörjad	Inga val

Klick → öppnar veckovy

C. Avdelningsinfo

Read-only kort:

avdelningsnamn
boendeantal
specialkost + antal
faktaruta
📅 Veckovy (valvy)

Visar:

veckans meny
alla dagar
Valbart
t.ex. lunchval / alternativ
Read-only
dessert
kvällsmat
Funktioner
göra val per dag
spara
“Klar vecka”-knapp
✅ Klar-logik

“Klar” är en explicit handling.

Sparas som:

completed_at
completed_by

Efter “Klar”:

status blir 🟢
kan låsas (eller kräva “Ångra klar”)
🧾 Statusmodell (teknisk)

Per:

department + week

Tillstånd:

ej påbörjad
påbörjad
klar
📊 Admin Dashboard-koppling

Visar:

“Menyval – kommande veckor”

Regel (pilot)

Avdelningar ska ligga minst 4 veckor fram.

Beräkning
hämta publicerade veckor
ta nästa 4
kontrollera vilka som saknar “klar”
Output

Exempel:

3 avdelningar ligger inte i fas

Avd A – saknar v.12, v.13  
Avd B – ej påbörjad
🧠 Viktig princip (V1)

Portalen påverkar planering
men räknar inget själv

🔵 Portal 2.0 – Future Lab
🎯 Ny roll

Portalen blir:

👉 en strukturerad inputmodul till Planera 2.0

🔄 Arkitekturskifte
V1
Portal → påverkar siffror direkt
V2
Portal → input  
Planera 2.0 → beräkning
🧱 Inputmodell

Portalen levererar:

department_id
service_day (DATE)
meal_key
selection_key
completed_at
📅 service_day (kritisk förändring)
V1
vecka + veckodag
V2
absolut datum
service_day = 2026-03-17

👉 UI visar vecka
👉 backend lagrar datum

🔄 4-veckorsregel (framtid)

Istället för:

"4 veckor fram"

Blir:

alla service_day < (idag + 28 dagar) ska vara completed
🧱 Föreslagen datamodell
department_service_selection

Fields:

department_id
site_id
service_day (DATE)
meal_key
selection_key
started_at
completed_at
completed_by
locked (bool)
Unik constraint
(department_id + service_day + meal_key)
🔌 Integration med Planera 2.0

Via:

PortalSelectionAdapter
🧪 Portalens roll

Portalen levererar:

vad som valts
när det valts
om det är klart

Motorn avgör:

produktion
kvantiteter
kategorier
🧭 Strategisk uppdelning
Pilot (Unified)
Portal V1
enkel logik
UI-fokus
stabilitet
Future Lab
Portal 2.0
ren datamodell
adapter till engine
kontextneutral
🚀 Implementationsstrategi
Nu (pilot)
bygg V1
koppla dashboard
håll enkel
GZ-tagga
Sen (2.0)
bygg engine
refaktorera portal → input layer
byt backend utan att ändra UI
🔥 Viktigaste insikten

Planera 2.0 är motorn
Avdelningsportalen är input

🧠 Strategisk roll

Portalen är:

operativ input
användargränssnitt
datakälla

Den möjliggör:

automatiserad planering
bättre datakvalitet
minskad manuell hantering
⚠️ Viktiga designprinciper
1. Ingen logik i UI

All logik:

→ Planera 2.0
2. Portal = input

Inte:

beräkning
beslut
3. Feature flags

Möjlighet att aktivera:

val
specialkost
framtida funktioner
4. Måste fungera utan portal

Planera ska fungera även utan denna modul.

✅ Sammanfattning

Avdelningsportalen är:

i pilot: ett enkelt valverktyg
i framtid: en central inputmodul

Den:

kopplar användare till systemet
strukturerar data
matar Planera 2.0