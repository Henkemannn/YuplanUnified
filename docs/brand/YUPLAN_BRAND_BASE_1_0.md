# Yuplan Brand Base 1.0

**Status:** CURRENT
**Version:** Augusti 2026
**Källa:** extern Source of Truth i Canva

Detta dokument är den mänskligt läsbara canonical brandkällan för Yuplan.
Om något i repo:t avviker från detta dokument ska detta dokument betraktas som styrande tills en uttrycklig migreringsgate uppdaterar implementationen.

## Brandidé

Yuplan ska upplevas som premium, tydlig och trygg i både light och dark. Varumärket ska signalera modern drift, kompetens och lugn precision, inte lekfull experimentdesign.

## Canonical paths

- Primary logo: `static/brand/v1/logo/yuplan-mark-primary.svg`
- Primary mascot: `static/brand/v1/mascot/yuplan-mascot-primary-2048.png`

## Logo / Identity Colors

Följande färger hör till själva logo-identiteten och ska användas för märket, inte automatiskt som produkt-/UI-token:

- `#3BA9E5`
- `#12B7A5`
- `#0AA090`
- `#FFD166`
- `#FFFFFF`

## Product / UI Colors

Följande färger hör till produktens UI och design system:

- Yuplan Teal: `#00AEB8`
- Yuplan Ocean: `#035590`
- Deep Ocean: `#071426`
- Signal Yellow: `#F1E15E`
- Yuplan Cyan: `#02AEC3`
- Yuplan Ink: `#101828`
- Yuplan Mist: `#EAF7F8`
- White: `#FFFFFF`

## Typografi

- Manrope

## Logotypregler

- Aktuell logotypidentitet är ett cirkulärt glob/grid-märke i teal/cyan.
- Märket ska ha ett vitt versalt Y.
- En liten gul accent ingår i identiteten.
- Originalfil ska användas utan egna visuella modifieringar.
- Inga äldre eller alternativa logovarianter får införas som ny brandreferens.
- Logo-paletten hör till märket.
- UI-paletten hör till produktens gränssnitt.
- Loggan ska inte automatiskt recoloras för att matcha UI-token.
- Light/Dark bygger på Product / UI Colors, inte på logo-paletten.

Viktigt: `static/img/logo-proposal.svg` har rätt grundidé, men använder äldre färger och är därför **ORIGINAL ANCESTOR / LEGACY IMPLEMENTATION**. Den är inte längre canonical asset.

## Mascot / helper-riktning

- Maskot är ännu inte verifierad som repo-asset.
- Profilen ska vara turkos, Ocean/Teal, med korrekt versalt Y.
- Maskoten ska kännas vänlig och kompetent.
- Den ska användas som diskret helper, inte som pynt.

## Light / Dark-riktning

- Yuplans framtida produkt-UI ska stödja både Light och Dark som en del av premiumkänslan.
- Detta är en låst brand- och produktprincip.
- Denna riktning ska inte implementeras i denna dokumentationsgate.

## Kända legacy-spår

Följande spår ska betraktas som legacy tills annat uttryckligen anges:

- `static/img/logo-proposal.svg` = ORIGINAL ANCESTOR / LEGACY IMPLEMENTATION
- Den gamla svartvita Y-loggan med tallrik i Y:et.
- YuplanBlue
- YuplanGreen
- YuplanDuotone
- YuplanDuotoneDark
- YuplanWordmark
- Liknande äldre eller experimentella varianter som inte uttryckligen refererar till Brand Base 1.0.
- Tallrik/bestick-loggor = DEPRECATED / DO NOT USE

## Användningsregel

- Gamla filer får ligga kvar för historik och referens.
- De får inte användas som ny designreferens.
- Nya brandbeslut ska alltid utgå från detta dokument.
