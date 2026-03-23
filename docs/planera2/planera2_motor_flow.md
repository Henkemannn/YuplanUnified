# Planera 2.0 – Motor Flow v1.0

## Syfte

Detta dokument definierar exakt hur Planera 2.0-motorn ska fungera.

Det är den definitiva pipeline som:

* styr implementation
* säkerställer korrekt beräkning
* möjliggör testbarhet

---

# 🧠 Översikt

Motorn tar en strukturerad input och producerar en deterministisk output.

```text
PlanRequest → Engine → PlanResult
```

---

# 📥 Input (PlanRequest)

PlanRequest innehåller tre delar:

## 1. Baseline

Totalt antal portioner

Ex:

* 50 luncher

---

## 2. Deviations

Lista av avvikelser

Varje deviation innehåller:

* form (obligatorisk)
* category_key (normaliserad)
* quantity
* optional: unit_id

Ex:

* timbal + ej_fisk → 3
* timbal + laktosfri → 2

---

## 3. Context

Beskriver struktur

* units (avdelningar/grupper)
* meal_key (lunch, middag)
* menu_option (val, ex alt_1/alt_2)

---

# 📤 Output (PlanResult)

Motorn returnerar:

* totals
* per_form
* per_combination
* per_unit
* warnings

---

# 🔁 Motor Flow (steg för steg)

## STEP 1 – Initiera struktur

Skapa tom resultstruktur:

* totals
* per_form = {}
* per_combination = {}
* per_unit = {}
* warnings = []

---

## STEP 2 – Validera input

Kontrollera:

* baseline >= 0
* alla deviations har:

  * form
  * category_key
  * quantity >= 0

Om fel:

* lägg till warning
* fortsätt (ingen crash)

---

## STEP 3 – Normalisera kategorier

Alla category_key ska:

* vara lowercase
* snake_case
* deterministiska

Ex:

* "Ej Fisk" → "ej_fisk"

---

## STEP 4 – Bygg kombinationsnycklar

Skapa unik nyckel:

```text
<form>__<category_key>
```

Ex:

* timbal__ej_fisk
* timbal__laktosfri

Om flera kategorier:

```text
timbal__ej_fisk__laktosfri
```

(sorterade alfabetiskt)

---

## STEP 5 – Summera deviations

Loopa över deviations:

För varje:

* lägg till i total_deviation
* summera per_form
* summera per_combination

---

## STEP 6 – Summera per unit (om finns)

Om unit_id finns:

* summera per_unit
* koppla till rätt kombination/form

---

## STEP 7 – Beräkna normal

```text
normal = baseline_total - deviation_total
```

Regel:

* normal får aldrig vara < 0
* om negativ:

  * sätt till 0
  * lägg warning

---

## STEP 8 – Bygg totals

Totals ska innehålla:

* baseline_total
* deviation_total
* normal_total

---

## STEP 9 – Sortera output

Alla dictionaries ska vara:

* deterministiskt sorterade
* samma ordning varje gång

---

## STEP 10 – Returnera resultat

Returnera:

* totals
* per_form
* per_combination
* per_unit
* warnings

---

# 🧪 Exempel (konkret)

## Input

Baseline:

* 50

Deviations:

* timbal + ej_fisk → 3
* timbal + laktosfri → 2

---

## Output

Totals:

* baseline: 50
* deviation: 5
* normal: 45

Per form:

* timbal: 5

Per combination:

* timbal__ej_fisk: 3
* timbal__laktosfri: 2

---

# ⚠️ Edge cases

## 1. Deviation > baseline

* normal = 0
* warning

---

## 2. Okänd kategori

* inkludera i output
* warning

---

## 3. Tom input

* returnera tom struktur
* inga krascher

---

# 🧠 Designregler (måste följas)

## Engine får inte:

❌ göra DB-anrop
❌ importera Flask
❌ använda UI
❌ innehålla kundspecifik logik

---

## Engine måste:

✔ vara ren funktion
✔ vara deterministisk
✔ vara testbar isolerat

---

# 🔧 Pseudokod (Copilot-ready)

```python
def compute_plan(request):
    result = init_result()

    validate(request)

    for dev in request.deviations:
        key = build_combination_key(dev)

        result.per_form[dev.form] += dev.quantity
        result.per_combination[key] += dev.quantity

        if dev.unit_id:
            result.per_unit[dev.unit_id] += dev.quantity

        result.deviation_total += dev.quantity

    result.normal = max(0, request.baseline - result.deviation_total)

    if result.normal == 0 and request.baseline < result.deviation_total:
        result.warnings.append("Deviation exceeds baseline")

    return sort_result(result)
```

---

# 🚀 Sammanfattning

Planera 2.0-motorn:

* tar baseline + deviations
* räknar produktion
* grupperar resultat
* returnerar tydlig struktur

Detta är grunden för:

* UI
* AI
* inköp
* recept
* projekt

---

# 🧷 Kort formulering

Input → Beräkning → Strukturerad output

Detta är hjärtat i hela Yuplan.
