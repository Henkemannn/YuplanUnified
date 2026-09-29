# Future Lab — Kostkrav, lämplighet och Planera-varningar

Status: Future concept / architecture note. Inte del av Kommun 1.1 och ska inte implementeras i nuvarande MVP-gate.

## Idé

Builder ska på sikt kunna beskriva mer än EU:s 14 allergener. Ett professionellt kök ska även kunna markera hur väl en canonical Component fungerar för verksamhetens registrerade kost- och konsistenskrav, till exempel:

- Timbal
- Grov paté
- Lättuggat
- Flytande kost
- andra lokalt definierade requirement types

Syftet är att skapa tydliga "alarmklockor" redan i Builder som senare kan användas av Planera 2.0 när en publicerad meny jämförs med de faktiska behoven på avdelningarna.

## Viktig princip

Detta ska INTE modelleras som allergener.

Allergenfakta beskriver innehåll, exempelvis:

- innehåller mjölk
- innehåller gluten

Lämplighetsmetadata beskriver i stället relationen mellan en Component och ett kost-/produktionskrav, exempelvis:

- Lämplig
- Kräver anpassning
- Ej lämplig
- Ej bedömd

Exempel:

Component: Köttbullar

- EU-allergener: gluten, mjölk
- Timbal: Kräver anpassning
- Grov paté: Kräver anpassning
- Lättuggat: Lämplig
- Flytande kost: Ej lämplig

## Arkitektur

### Component är primär ägare

Compatibility/lämplighetsinformationen bör i första hand ägas av canonical Component.

Skäl:

- Dish består av Components.
- Problemet uppstår ofta i en specifik komponent.
- Planera kan senare peka ut exakt vilken del av rätten som orsakar konflikt.
- Samma Component kan återanvändas i flera Dishes.

### Dish ska kunna summera

Dish bör kunna härleda en sammanfattning från sina Components.

Exempel:

Dish: Köttbullar med gräddsås och potatis

Om såsen är "Ej lämplig" för ett krav ska Dish kunna visa en varning men samtidigt ange vilken Component som orsakar den.

Manuell Dish-override bör endast införas om ett verkligt behov finns och semantiken är tydlig.

## Verksamhetens krav ska styra

Builder Core ska inte hårdkoda kommunala begrepp som Timbal eller Grov paté.

Den generella modellen ska utgå från verksamhetens registrerade requirement types.

Det innebär:

- Kommun kan ha Timbal, Grov paté, Flytande osv.
- Ett annat kommunalt kök kan ha en annan uppsättning.
- Offshore eller framtida verksamheter kan använda andra krav.
- Builder och Planera förblir generiska.

## Framtida Planera 2.0-flöde

Önskad kedja:

Publicerad meny
→ Dish
→ Components
→ allergener + kost/lämplighetsmetadata
→ registrerade behov på avdelningarna
→ Planera 2.0 analys
→ varning/förslag
→ mänskligt beslut
→ produktionsunderlag

Exempel:

> Köttbullar — Avd 13  
> 2 portioner Timbal  
> Komponenten "Köttbullar" är markerad "Kräver anpassning för Timbal".  
> Granska anpassning.

Planera ska i första hand varna och föreslå. Kocken/planeraren fattar beslutet.

## Relation till allergener

Allergen- och compatibility-metadata ska hållas separata men kunna presenteras tillsammans i användarflödet.

Exempel:

- Allergen: "Innehåller mjölk"
- Kostkrav: "Ej lämplig för Timbal"

De betyder olika saker och ska inte använda samma datamodell enbart för att de båda kan skapa en varning.

## Möjlig framtida UI-riktning

I shared Component editor kan ett framtida område heta exempelvis:

**Kost & anpassningar**

Där visas endast requirement types som är relevanta för aktuell verksamhet/site/tenant.

Varje krav kan få status:

- Ej bedömd
- Lämplig
- Kräver anpassning
- Ej lämplig

UI ska vara snabbt nog för köksarbete och tablet/iPad.

## Produktvärde

Detta gör att Yuplan på sikt kan gå från att enbart veta *hur många specialkoster som behövs* till att även förstå *om den planerade maten faktiskt är kompatibel med människorna som ska äta den*.

Det skapar en stark koppling mellan:

- Builder
- Meny
- registrerade behov
- Planera 2.0
- produktionsunderlag

## Ej nu

Följande är uttryckligen utanför Kommun 1.1:

- ny compatibility-datamodell
- migrationer
- Planera-varningsmotor
- automatisk menyadaptation
- hardcoded kommunala kosttyper i Builder Core
- generisk regelmotor

Idén ska tas upp i en senare Builder/Planera-fas efter MVP/pilot.
