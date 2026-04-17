📄 AI Assist & Data Truth Principles – Yuplan Platform
🎯 Syfte

Detta dokument definierar hur Yuplan ska hantera:

datans sanning (“source of truth”)
AI-assistans
import och automatisering

Målet är att:

säkerställa hög datakvalitet
möjliggöra AI-stöd utan att förlora kontroll
bygga ett system som är både smart och pålitligt
🧠 Kärnprincip

AI får hjälpa till
men AI får aldrig vara sanningen

🔑 Grundprinciper
1. All affärskritisk data måste vara explicit godkänd

Data som påverkar:

produktion
specialkost
inköp
kostnad

måste alltid:

skapas av användare
eller
godkännas av användare
2. AI är alltid ett förslag

AI får:

tolka text
föreslå komponenter
föreslå compositions
föreslå ingredienser
föreslå receptstruktur
föreslå förbättringar

AI får aldrig:

automatiskt skriva över data
ändra befintliga värden utan godkännande
skapa “sanning” utan mänsklig kontroll
3. Tydlig separation: Sanning vs Förslag

Systemet ska tydligt skilja mellan:

CONFIRMED DATA
vs
AI SUGGESTED DATA

Exempel:

komponent kopplad via användare → sanning
komponent föreslagen av AI → förslag
4. Alla AI-flöden ska vara granskningsbara

Varje AI-baserad funktion ska ha:

preview-läge
möjlighet att redigera
tydlig “godkänn”-handling

Exempel:

Import → AI-tolkning → preview → användare godkänner → sparas
5. AI får aldrig bryta datamodellen

AI får inte skapa:

fria textfält där struktur krävs
komponenter utan component_id
ingredienser utan mängd/enhet
ogiltiga relationer mellan objekt

AI måste alltid respektera:

component → composition → recipe → ingredient-strukturen
🧱 Data Truth Model
Sanningshierarki
Component → SANNING (identitet)
Recipe → SANNING (metod, default styr kalkyl)
Ingredient line → SANNING (vad som används)
Menu/Composition → SANNING (struktur)
AI:s roll
AI → endast assistanslager ovanpå sanningen
🔄 AI-användningsområden i Yuplan
1. Menyimport

AI kan:

tolka text
identifiera möjliga components
föreslå compositions

Men:

unresolved ska användas vid osäkerhet
användaren måste bekräfta
2. Receptimport

AI kan:

tolka ingrediensrader
extrahera mängd + enhet
strukturera recept

Men:

resultatet måste granskas
felaktiga tolkningar får inte sparas automatiskt
3. Bild / handskriven input

AI kan:

läsa handskrivna recept
tolka bilder

Men:

alltid som förslag
aldrig direkt in i systemets kärndata
4. Smarta förslag (framtid)

AI kan föreslå:

liknande compositions
komponentbyten
samproduktion (“du lagar detta imorgon också”)
kostnadsoptimering

Men:

beslut tas alltid av användaren
⚠️ Kritiska risker (som ska undvikas)
❌ 1. “AI vet bäst”

→ leder till felaktig data
→ förstör förtroende

❌ 2. Automatisk överskrivning

→ användare tappar kontroll
→ svårt att spåra fel

❌ 3. Otydlig AI vs manuell data

→ användaren vet inte vad som är säkert
→ skapar osäker drift

❌ 4. För aggressiv automation tidigt

→ systemet känns “magiskt” men opålitligt

🧠 Designprincip

Yuplan ska vara:

strukturdriven
användarkontrollerad
AI-assisterad

Inte:

AI-styrd
🔐 Golden Rule

All data som påverkar produktion eller ekonomi måste kunna spåras till ett medvetet beslut

🚀 Strategisk effekt

Denna modell gör att Yuplan kan:

använda AI aggressivt utan att riskera datakvalitet
bygga avancerade funktioner ovanpå stabil data
behålla förtroende i kritiska miljöer (kök, offshore, vård)
✅ Sammanfattning
AI är ett verktyg, inte en beslutsfattare
Data måste vara explicit godkänd
Struktur får aldrig brytas
Alla AI-flöden ska gå via preview och godkännande
Yuplan bygger på kontroll + assistans