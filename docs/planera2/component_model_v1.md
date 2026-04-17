# Planera 2.0 – Component Model v1

## 🎯 Syfte

Definiera den första versionen av komponentmodellen i Planera 2.0.

En komponent är den centrala byggstenen i Yuplan och ska möjliggöra:
- återanvändning över menyer och dagar
- koppling till recept, allergener, prep, frysplock, inköp och kostnad
- framtida AI-stöd och optimering

Detta dokument definierar en **minimal, framtidssäker modell** utan att påverka nuvarande engine.

---

## 🧱 Definition – Vad är en komponent?

En komponent är:

> En återanvändbar produktionsbyggsten som kan ingå i flera måltider och sammanhang.

### Exempel:
- Köttbullar
- Potatis
- Tomatsås
- Majonässås
- Fisktimbal

---

## 🚫 Vad en komponent INTE är

En komponent är inte:
- en färdig måltid
- en dagsplanering
- en rad i Planera
- en avdelningsspecifik mängd
- en menyplats (lunch/kväll)

---

## 🧩 Relation till måltid

En måltid är:

> En sammansättning av flera komponenter

Exempel:
- Köttbullar + potatis + gräddsås
- Fisk + ris + kall sås

👉 Komponent = byggsten  
👉 Måltid = komposition

---

## 🏷️ Minimal datamodell (v1)

### Kärnfält

- `component_id`  
  Stabilt och unikt ID (kärnan i hela modellen)

- `canonical_name`  
  Primärt namn (t.ex. "Köttbullar")

- `is_active`  
  Om komponenten är aktiv eller arkiverad

---

### Tidiga tillägg (rekommenderade)

- `default_uom`  
  Basenhet (t.ex. portion, kg)

- `tags`  
  Flexibla etiketter (t.ex. "kött", "sås", "timbal")

- `categories`  
  Valfri gruppering (skapas av användaren)

---

## ⚠️ Medvetet utelämnat i v1

Följande ingår inte ännu:

- recept
- allergener
- inköp / artikelnummer
- kostnad
- prep / fryslogik
- versionering

👉 Dessa kommer i senare lager

---

## 🧠 Designprinciper

### 1. Stabil identitet
`component_id` ska aldrig ändras.

### 2. Återanvändbarhet
Samma komponent ska kunna användas i:
- olika menyer
- olika dagar
- olika kök

### 3. Ingen hårdkodad kategorisering
Kategorier ska vara:
- flexibla
- användardefinierade

### 4. Separation av ansvar

| Lager | Ansvar |
|------|--------|
| Component | Identitet + metadata |
| Planera | Beräkning av behov |
| Composition (senare) | Hur komponenter kombineras |
| Recipes (senare) | Hur komponenter tillagas |

---

## 🔗 Relation till Planera 2.0 (nuvarande)

Just nu:

- Engine bryr sig inte om komponenter
- Planering sker via baseline + deviations

Framåt:

- komponenter kommer in via **context**
- engine förblir compute-only
- komponentlogik byggs ovanpå

### Minimal context-konvention (v1, optional)

För tidig, säker context-bäring används följande valfria nycklar:

```json
{
  "component_id": "meatballs",
  "component_name": "Köttbullar"
}
```

Regler:
- Helt valfritt (kan utelämnas)
- Ingen beräkningslogik i engine baseras på dessa fält i detta steg
- Metadata får endast passeras vidare om den uttryckligen finns (ingen gissning)

### Component Context Semantics v1

Utöver `component_id` och `component_name` kan context bära två valfria semantikfält:

- `component_role`
  - avsedd roll i planeringssammanhang
  - exempel: `main`, `side`, `sauce`, `dessert_component`, `other`

- `component_mode`
  - beskriver hur komponentmetadata ska tolkas i detta steg
  - `informational` betyder att metadata endast är vägledande och inte styr beräkning

Regel i v1:
- om `component_id` finns men `component_mode` saknas, sätts `component_mode = informational`
- engine förblir compute-only och opåverkad av komponentsemantik i detta steg

---

## 🧭 Migration path

### Steg 1 (nu)
- Definiera komponentbegreppet
- Dokumentera modell (detta dokument)

### Steg 2
- Introducera komponentkatalog (read-only)

### Steg 3
- Koppla komponent_id till planeringsdata (context)

### Steg 4
- Skapa kompositionslager (måltid = komponenter)

### Steg 5
- Koppla på:
  - recept
  - allergener
  - prep
  - frysplock
  - inköp

---

## 🚀 Långsiktig vision

Komponentmodellen möjliggör:

- menybyggare (drag & drop)
- produktionsoptimering
- inköpsautomation
- kostnadsberäkning
- AI-rekommendationer
- svinnreducering

---

## ✅ Beslut (låst)

- "Komponent" är kärnbegrepp
- Måltider byggs av komponenter
- Modellen ska vara generell (kommun, offshore, hotell, bankett)
- Implementation sker stegvis
- Engine påverkas inte i detta steg