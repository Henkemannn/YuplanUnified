# Planera 2.0 – Teknisk Arkitektur (v1)

## Syfte

Planera 2.0 är Yuplans centrala planeringsmotor.

Den ska vara:

* generell (inte bunden till en kundtyp)
* deterministisk (samma input → samma output)
* testbar (utan UI och databas)
* utbyggbar (för framtida funktioner som AI, inköp, recept)

---

# 🧱 Övergripande arkitektur

Planera 2.0 består av tre lager:

## 1. Engine (kärnan)

Ansvar:

* all beräkning
* ingen beroende till UI
* ingen databaslogik
* ingen Flask / routing

Egenskaper:

* ren funktion: input → output
* deterministisk
* testbar i isolation

---

## 2. Adapters (översättningslager)

Ansvar:

* hämta data från systemet
* översätta till engine-format

Exempel:

* kommun-adapter
* offshore-adapter
* hotell/ad-hoc adapter

Adapters gör:

* registreringar → deviations
* boendeantal → baseline
* menyval → context

---

## 3. Application Layer

Ansvar:

* anropa adapters
* anropa engine
* returnera resultat till UI/API

---

# 📥 Inputmodell (PlanRequest)

Planera 2.0 tar emot en standardiserad input:

## Baseline

Totalt antal portioner

Ex:

* 50 luncher

---

## Deviations

Lista av avvikelser från baseline

Varje deviation innehåller:

* form (obligatorisk för specialkost)
* kategori (normaliserad key)
* antal

Ex:

* timbal + ej_fisk → 3
* timbal + laktosfri → 2

---

## Context

Beskriver struktur:

* enheter (avdelningar / grupper)
* menyval (Alt 1 / Alt 2 eller motsvarande)
* måltid (lunch, middag etc.)

---

# 📤 Outputmodell (PlanResult)

Motorn returnerar:

## 1. Totalt

* baseline
* deviation_total
* normal

---

## 2. Produktion per form

Ex:

* timbal: 8
* flytande: 2

---

## 3. Produktion per kombination

Ex:

* timbal__ej_fisk: 3
* timbal__laktosfri: 2

---

## 4. Produktion per enhet

Ex:

* avdelning A: 12
* avdelning B: 8

---

## 5. Warnings

Ex:

* okänd kategori
* inkonsekvent data

---

# 🧠 Kärnlogik

Grundformel:

```
baseline_total = alla portioner
deviation_total = summa av alla avvikelser
normal = baseline_total - deviation_total
```

---

# 🔁 Beräkningsprincip

Motorn arbetar:

1. Läs baseline
2. Läs deviations
3. Normalisera kategorier
4. Bygg kombinationsnycklar
5. Summera per form
6. Summera per kombination
7. Summera per enhet
8. Beräkna normal
9. Generera warnings
10. Returnera resultat

---

# 🔑 Viktiga principer

## 1. Compute-first

* inget sparat resultat
* allt beräknas varje gång

---

## 2. Determinism

* samma input → samma output
* sorterad output
* inga tidsberoenden

---

## 3. Normaliserade nycklar

* alla kategorier via central funktion
* snake_case
* inga fria strängar

---

## 4. Separation av ansvar

Engine:

* räknar

Adapters:

* hämtar data

UI:

* visar data

---

## 5. Ingen kundlogik i engine

Engine får aldrig innehålla:

* Alt 1 / Alt 2 direkt
* avdelningstyper
* specifika verksamhetsregler

---

# ⚠️ Edge cases

## Okända kategorier

* returnera warning
* inkludera i output om möjligt

---

## Deviation > baseline

* normal får aldrig bli negativ
* clamp till 0
* warning genereras

---

## Tom input

* returnera tom struktur
* inga krascher

---

# 🧪 Teststrategi

Motorn ska testas med:

* fasta inputs
* förväntade outputs
* jämförelse (golden tests)

---

# 🚫 Vad ingår INTE (P0)

Följande ligger utanför Planera 2.0 v1:

* recept
* ingredienser
* inköp
* lager/frys
* projekt
* pris/kalkyl
* AI-logik

---

# 🔮 Design för framtiden

Motorn ska kunna utökas med:

* receptkoppling
* ingrediensanalys
* allergimotor
* inköpsmotor
* lager/frys
* AI-assistent

---

# 📦 Sammanfattning

Planera 2.0 byggs som:

* en ren beräkningsmotor
* med tydlig input/output
* separerad från UI och databas
* redo för framtida expansion

Detta är grunden för hela Yuplans framtida funktionalitet.
