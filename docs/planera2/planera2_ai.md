# Planera 2.0 + AI – Roll & Framtidsplan

## Syfte

Detta dokument beskriver hur AI ska användas i Planera 2.0.

Målet är att bygga ett system som är:

* tryggt
* förutsägbart
* kraftfullt
* framtidssäkert

---

# 🧠 Grundprincip

Planera 2.0 består av två tydliga lager:

## 1. Regelmotor (kärnan)

Ansvarar för:

* beräkning av produktion
* hantering av baseline och avvikelser
* korrekt output till köket

Egenskaper:

* deterministisk
* testbar
* spårbar
* utan AI
* alltid korrekt och förutsägbar

---

## 2. AI-lager (assistans)

Ansvarar för:

* analys
* varningar
* förbättringsförslag
* optimering

AI är ett stöd – inte en ersättning för kärnlogiken.

---

# ⚖️ Rollfördelning

| Funktion              | Regelmotor | AI             |
| --------------------- | ---------- | -------------- |
| Räkna produktion      | ✅          | ❌              |
| Hantera avvikelser    | ✅          | ❌              |
| Ge varningar          | ⚠️ (enkla) | ✅ (avancerade) |
| Föreslå förbättringar | ❌          | ✅              |
| Optimera              | ❌          | ✅              |

---

# 🎯 Varför denna uppdelning?

I köksmiljö är det kritiskt att:

* allergier hanteras korrekt
* produktion är exakt
* resultat går att förklara

AI är stark på:

* mönsterigenkänning
* språk
* förslag

Men svagare på:

* exakta beräkningar
* full spårbarhet
* deterministiskt beteende

Därför:

👉 Regelmotor = sanning
👉 AI = rådgivare

---

# 🔮 Vad AI ska kunna göra (framtid)

## 1. Riskanalys (mycket viktig)

Exempel:

* recept innehåller majonnäs
* majonnäsen innehåller cayenne
* cayenne kan påverka paprikaallergi

AI ska kunna varna:

"Kontrollera detta – möjlig allergirisk"

---

## 2. Receptanpassning

AI ska kunna:

* föreslå alternativa ingredienser
* föreslå tillagningsändringar
* skapa specialkostvarianter

---

## 3. Inköpsoptimering

AI ska kunna:

* analysera historisk data
* se lager och frys
* föreslå beställningar
* varna för svinn

---

## 4. Produktionsoptimering

AI ska kunna:

* föreslå effektivare upplägg
* upptäcka överproduktion
* föreslå batchning

---

## 5. Kalkyl & pris

AI ska kunna:

* räkna kostnad per portion
* föreslå prisnivå
* analysera marginal

---

## 6. Projektstöd (bankett/event)

AI ska kunna:

* hjälpa till att bygga meny
* uppskatta behov
* skapa checklistor
* identifiera risker

---

## 7. Statistik & lärande

AI ska kunna:

* identifiera mönster
* analysera användning
* ge förbättringsförslag

---

# 🧱 AI-nivåer (utvecklingssteg)

## Nivå 1 – Assistent (första steg)

* warnings
* enkla förslag
* textbaserad hjälp

---

## Nivå 2 – Analys

* djupare mönsteranalys
* optimering
* rekommendationer

---

## Nivå 3 – Automation

* generera inköpslistor
* skapa projektförslag
* automatisera planeringsflöden

---

# 🧬 AI-ready design (viktigt)

Planera 2.0 måste byggas så att AI kan användas senare.

Det innebär att systemet ska kunna hantera:

* menydata
* produktionsdata
* avvikelser
* recept (framtid)
* ingredienser
* allergener
* historik
* kostnader

---

# ⚠️ Viktiga regler

AI får:

✔ föreslå
✔ varna
✔ analysera
✔ optimera

AI får inte:

❌ ändra produktion automatiskt
❌ ersätta kärnlogik
❌ ta beslut utan kontroll

---

# 🧠 Designprincip

All AI-integration ska ske via tydliga lager:

* engine påverkas inte
* AI läser output + data
* AI returnerar rekommendationer

---

# 🔄 Dataflöde

1. Engine räknar produktion
2. Resultat skickas till AI-lager
3. AI analyserar
4. AI returnerar:

   * warnings
   * förslag
   * förbättringar

---

# 📦 Exempel

## Input

* meny
* avvikelser
* recept

## Engine

* räknar produktion

## AI

* analyserar recept
* upptäcker risk
* föreslår ändring

## Output

* produktion + AI-insikter

---

# 🚀 Sammanfattning

Planera 2.0 byggs som en stabil och trygg kärna.

AI byggs ovanpå som en intelligent assistent.

Detta gör att systemet:

* är pålitligt från start
* kan bli smartare över tid
* kan växa utan att byggas om

---

# 🧷 Kort formulering

Planera 2.0 = hjärnan
AI = rådgivaren

Tillsammans skapar de ett komplett system för framtidens köksplanering.
