# Avdelningsportal – Veckovy (Department Portal Week) – JSON Schema

## Endpoint (Phase 1 Read-Only)
GET /portal/department/week?year=YYYY&week=WW

- `department_id` kommer inte som query-parameter; hämtas från autentisering (role `department_user`), token innehåller `department_id`.

## Request
- Query params:
  - `year` (int, 2000–2100)
  - `week` (int, 1–53)
- Auth: Bearer token med roll `department_user` och ett bundet `department_id`.

## Response – Top-Level Shape
```json
{
  "department_id": "uuid",
  "department_name": "Avd 1",
  "year": 2025,
  "week": 47,
  "site_id": "uuid",
  "site_name": "Midsommargården",
  "facts": {
    "note": "Inga risrätter",
    "residents_default_lunch": 10,
    "residents_default_dinner": 8
  },
  "progress": {
    "days_with_choice": 5,
    "total_days": 7
  },
  "etag_map": {
    "menu_choice": "W/\"menu-choice:...\"",
    "weekview": "W/\"weekview:...\""
  },
  "days": [
    {
      "date": "2025-11-17",
      "weekday_name": "Måndag",
      "menu": {
        "lunch_alt1": "Köttbullar med potatis",
        "lunch_alt2": "Fiskgratäng",
        "dessert": "Pannacotta",
        "dinner": "Smörgås och soppa"
      },
      "choice": {
        "selected_alt": "Alt1"
      },
      "flags": {
        "alt2_lunch": true
      },
      "residents": {
        "lunch": 10,
        "dinner": 8
      },
      "diets_summary": {
        "lunch": [
          { "diet_type_id": "gluten", "diet_name": "Gluten", "count": 2 },
          { "diet_type_id": "laktos", "diet_name": "Laktos", "count": 1 }
        ],
        "dinner": []
      }
    }
  ]
}
```

### Fältbeskrivning
- `department_id`: UUID för avdelningen.
- `department_name`: Visningsnamn.
- `year`, `week`: Kalender-vecka.
- `site_id`, `site_name`: Kopplad site/boende.
- `facts`: Metadata (anteckning + default-resident-räkningar) – read-only i fas 1.
- `progress`: Enkel progressindikator (antal dagar med val).
- `etag_map.menu_choice`: Weak ETag för menyvalsdata (mutationer kommer använda denna i senare fas).
- `etag_map.weekview`: Weak ETag för weekview-relaterad data (read-only här; caching och 304 senare).
- `days`: Lista med dagsobjekt.
  - `date`: ISO datum (YYYY-MM-DD).
  - `weekday_name`: Lokaliserat namn (t.ex. "Måndag").
  - `menu`: Menykomponenter för lunch alt1/alt2, dessert, dinner.
  - `choice.selected_alt`: "Alt1" | "Alt2" | null (om inget val ännu).
  - `flags.alt2_lunch`: Boolean som speglar alt2 driftstatus (från weekview alt2 flag).
  - `residents.lunch` / `residents.dinner`: Nuvarande boenderäkningar (read-only i fas 1).
  - `diets_summary.lunch` / `diets_summary.dinner`: Lista av dietobjekt med räknare.

### Skillnad mot Legacy
- `selected_alt` ersätter diffus `markerad`.
- Alt2 flagga separeras (driftstatus) och påverkar inte direkt om Alt2 kan väljas (regler kan införas senare).

## Mutation Schema (För senare fas)
### Endpoint (föreslagen):
POST /portal/department/menu-choice/change

### Body
```json
{
  "year": 2025,
  "week": 47,
  "weekday": "Mon",          // Standardiserad kortform (Mon, Tue, Wed, Thu, Fri, Sat, Sun) eller numerisk; beslut dokumenteras här.
  "selected_alt": "Alt1",     // "Alt1" | "Alt2"
  "if_match": "W/\"menu-choice:...\""
}
```

### Response
```json
{
  "new_etag": "W/\"menu-choice:v2\"",
  "selected_alt": "Alt1"
}
```

### Felkoder
- 400: Ogiltig weekday eller selected_alt.
- 404: Avdelning/vecka saknas.
- 412: ETag mismatch (If-Match fel) – klient bör refetcha payload.

## ETag Strategi
- `etag_map.menu_choice`: Används vid menyvalsmutationer; klient skickar värdet i `If-Match` eller body-fält `if_match` (strategi väljs; rekommenderat standard `If-Match` header).
- `etag_map.weekview`: Read-only i fas 1; kan användas i framtiden för conditional GET (304) på komposit-endpoint.
- Weak ETags räcker då payload inte kräver byte-range differenser.

## Komplett Exempel (2 dagar)
```json
{
  "department_id": "11111111-2222-3333-4444-555555555555",
  "department_name": "Avd 1",
  "year": 2025,
  "week": 47,
  "site_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "site_name": "Midsommargården",
  "facts": {
    "note": "Inga risrätter",
    "residents_default_lunch": 10,
    "residents_default_dinner": 8
  },
  "progress": {
    "days_with_choice": 1,
    "total_days": 7
  },
  "etag_map": {
    "menu_choice": "W/\"menu-choice:dept:11111111:v4\"",
    "weekview": "W/\"weekview:dept:11111111:year:2025:week:47:v9\""
  },
  "days": [
    {
      "date": "2025-11-17",
      "weekday_name": "Måndag",
      "menu": {
        "lunch_alt1": "Köttbullar med potatis",
        "lunch_alt2": "Fiskgratäng",
        "dessert": "Pannacotta",
        "dinner": "Smörgås och soppa"
      },
      "choice": { "selected_alt": "Alt1" },
      "flags": { "alt2_lunch": true },
      "residents": { "lunch": 10, "dinner": 8 },
      "diets_summary": {
        "lunch": [
          { "diet_type_id": "gluten", "diet_name": "Gluten", "count": 2 },
          { "diet_type_id": "laktos", "diet_name": "Laktos", "count": 1 }
        ],
        "dinner": []
      }
    },
    {
      "date": "2025-11-18",
      "weekday_name": "Tisdag",
      "menu": {
        "lunch_alt1": "Lasagne",
        "lunch_alt2": "Grönsakslasagne",
        "dessert": "Fruktsallad",
        "dinner": "Gröt"
      },
      "choice": { "selected_alt": null },
      "flags": { "alt2_lunch": false },
      "residents": { "lunch": 10, "dinner": 8 },
      "diets_summary": { "lunch": [], "dinner": [] }
    }
  ]
}
```

## Öppna Beslut / TODO
- Weekday representation i mutation (`Mon` vs siffra). Förslag: numerisk (1–7) för konsekvens med befintliga tabeller; dokumenteras när endpoint implementeras.
- Om alt2_lunch måste vara true för att "Alt2" ska kunna väljas (affärsregel i senare fas) – ej i Phase 1.
- Fält för historik/ändringsspårning kan adderas i framtiden.

## Sammanfattning
Detta schema formaliserar komposit-responsen för avdelningsportalen vecka och etablerar ett stabilt kontrakt innan endpoints och UI byggs. Mutation-kontrakt är definierat proaktivt men inte implementerat i Phase 1.
