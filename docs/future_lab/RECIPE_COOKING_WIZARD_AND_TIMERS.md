# Future Lab — Recept Live / Cooking Wizard

Status: Future concept / product direction. Inte del av Kommun 1.1 och ska inte implementeras i nuvarande shared editor-gate.

## Idé

Yuplan ska på sikt skilja tydligt mellan två sätt att arbeta med recept:

1. **Redigera recept** — i Builder / shared Component editor.
2. **Laga recept / Live** — ett separat fullskärmsläge för faktisk produktion i köket.

Editorn används för att skapa och underhålla ingredienser, mängder, metod och övrig receptdata.

Live-läget används när personalen faktiskt lagar receptet och ska därför vara touch-first, tydligt, stegvis och anpassat för surfplatta i köksmiljö.

## Cooking Wizard

Ett recept ska kunna köras som en wizard där metoden delas upp i tydliga arbetssteg.

Exempel:

**Steg 1 av 7**  
Väg upp mjöl, vatten och jäst.

→ Nästa

**Steg 2 av 7**  
Blanda degen i 8 minuter.

→ Nästa

**Steg 3 av 7**  
Låt degen jäsa i 20 minuter.

→ Nästa

Målet är att personalen inte ska behöva läsa ett långt metodfält och själv hålla reda på var i processen de befinner sig.

## Inbyggda timers

Metodsteg som innehåller en tidsberoende aktivitet ska kunna erbjuda en direkt timer.

Exempel:

> Låt brödet jäsa i 20 minuter  
> [ Starta 20 min ]

När timern startas ska den vara knuten till det aktuella receptet/steget och kunna ge tydlig återkoppling när tiden är slut.

Potentiella användningsfall:

- jäsning
- koktid
- stektid
- vilotid
- nedkylning
- mixer-/maskintid
- marinering
- regenerering

Det bör senare undersökas om en stabil befintlig open-source timerkomponent kan återanvändas i stället för att bygga all timerlogik från grunden. Eventuell tredjepartslösning ska granskas för licens, underhåll, tillgänglighet och offline-/PWA-beteende innan införande.

## UI-princip

Cooking Live ska vara en separat produktionsyta och inte pressas in i den vanliga recepteditorn.

Tänk:

- fullskärm
- stora touchmål
- ett tydligt steg i taget
- nästa/föregående
- tydlig progress
- aktiva timers
- portions-/batchkontext
- lätt att använda med smutsiga händer / snabb touch
- hög läsbarhet på iPad/tablet

## Långa recept

Editorn behöver inte försöka visa allt på en skärm.

Ett recept med många ingredienser får scrolla vertikalt. Även mycket stora recept ska kunna hanteras utan att editor-modalen växer okontrollerat.

Cooking Wizard löser en annan uppgift: där visas bara det som behövs i det aktuella arbetssteget.

## Framtida möjligheter

Inte beslutade, men naturliga framtida expansionspunkter:

- flera samtidiga timers per recept
- timer-notiser
- check-off på färdiga moment
- portions-/batchskalning
- temperaturmål
- HACCP-/egenkontrollspunkter
- foton eller platingreferenser
- ansvarig station/person
- paus/återuppta
- flera parallella recept i produktion
- köksöversikt över aktiva timers och steg

## Arkitekturprincip

Receptdata ska fortsatt ägas av canonical Component/Recipe-lagret.

Live-läget ska konsumera publicerad/sparad receptinformation och skapa temporärt kör-state för produktionen.

Det ska inte bli en separat kopia av receptet.

## Ej nu

Följande är utanför nuvarande Kommun 1.1 / shared editor UX-gate:

- Cooking Wizard runtime
- timerimplementation
- tredjepartsplugin
- produktionssessioner
- nya receptmodeller
- receptmigration från legacy Builder
- notifications
- HACCP-flöden

Idén tas upp i en senare Builder / Production / Planera-fas efter MVP/pilot.
