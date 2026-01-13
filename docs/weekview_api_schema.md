# Weekview API — Phase 1 (Read-only) → Phase 2 (Diets)

This document defines the JSON payload returned by `GET /api/weekview` for Phase 1 (read-only UI), and extensions in Phase 2 (diets). The payload remains backwards-compatible — existing keys are preserved (`marks`, `residents_counts`, `alt2_days`).

- ETag: The response includes an ETag header of the form `W/"weekview:dept:<department_id>:year:<yyyy>:week:<w>:v<version>"`.
- Conditional GET: Send `If-None-Match` to receive `304 Not Modified` when the version matches.

## Example Response (Phase 2 shows `diets` under each day)

```
{
  "year": 2025,
  "week": 45,
  "week_start": null,
  "week_end": null,
  "department_summaries": [
    {
      "department_id": "00000000-0000-0000-0000-000000000000",
      "department_name": null,
      "department_notes": [],
      "days": [
        {
          "day_of_week": 1,
          "date": "2025-11-03",
          "weekday_name": "Mon",
          "menu_texts": {
            "lunch": { "alt1": "Köttbullar", "alt2": "Fiskgratäng", "dessert": "Pannacotta" },
            "dinner": { "alt1": "Soppa", "alt2": "Pasta" }
          },
          "alt2_lunch": true,
          "residents": { "lunch": 42, "dinner": 18 },
          "diets": {
            "lunch": [
              { "diet_type_id": "gluten", "diet_name": "gluten", "resident_count": 2, "marked": true },
              { "diet_type_id": "laktos", "diet_name": "laktos", "resident_count": 1, "marked": false }
            ],
            "dinner": [
              { "diet_type_id": "gluten", "diet_name": "gluten", "resident_count": 2, "marked": false }
            ]
          }
        },
        { "day_of_week": 2, "date": "2025-11-04", "weekday_name": "Tue", "menu_texts": {"lunch": {"alt1": "Lasagne"}}, "alt2_lunch": false, "residents": {"lunch": 40, "dinner": 0} }
        // ... days 3..7
      ],
      "marks": [
        { "day_of_week": 1, "meal": "lunch", "diet_type": "veg", "marked": true }
      ],
      "residents_counts": [
        { "day_of_week": 1, "meal": "lunch", "count": 42 }
      ],
      "alt2_days": [1, 5]
    }
  ]
}
```

## Field Reference

- `year`/`week`: ISO year and week.
- `department_summaries[]`: Array of department-specific data for the requested context.
  - `department_id`: UUID.
  - `days[]`: Seven items (Mon..Sun), each containing:
    - `day_of_week`: 1..7 (Mon=1).
    - `date`: ISO-8601 date (computed via ISO week), or null if invalid.
    - `weekday_name`: Mon|Tue|Wed|Thu|Fri|Sat|Sun (for convenience only).
    - `menu_texts`: Optional object with available meals/variants for the day.
      - `lunch`/`dinner`: Optional objects when data exists.
        - `alt1`/`alt2`/`dessert`: Strings when present.
    - `alt2_lunch`: Boolean, whether lunch uses Alt2 that day (mirrors `alt2_days`).
    - `residents`: Aggregated expected counts per meal.
      - `lunch`/`dinner`: integers (default 0).
    - `diets` (Phase 2): Object with arrays per meal.
      - `lunch`/`dinner`: arrays of diet rows `{ diet_type_id, diet_name, resident_count, marked }`.
        - `diet_type_id`: string identifier for diet type (legacy kosttyp id/slug)
        - `diet_name`: human label (Phase 2.A uses id as placeholder; may join real name later)
        - `resident_count`: department default count for the diet type (from admin diet defaults)
        - `marked`: whether this diet required preparation for this day/meal
  - `marks`: Existing raw per-diet selections for cells.
  - `residents_counts`: Existing flattened counts per (day, meal).
  - `alt2_days`: Existing list of days (1..7) where Alt2 applies to lunch.

## Notes

- Backward compatibility: No existing keys were removed. New clients can consume `days[]` including `diets`, older clients can continue using `marks`, `residents_counts`, and `alt2_days`.
- ETag semantics: ETag reflects Weekview registration/alt2/resident changes. Menu text changes currently do not affect ETag (will be revisited when menu editing is integrated).

## PATCH /api/weekview/specialdiets/mark (Phase 2)

Toggle a single special diet mark for a given date/meal/diet.

Request JSON:

```
{
  "site_id": "<uuid>",
  "department_id": "<uuid>",
  "local_date": "2025-11-03",
  "meal": "lunch",
  "diet_type_id": "gluten",
  "marked": true
}
```

Headers: `If-Match: W/"weekview:dept:<id>:year:<yyyy>:week:<ww>:v<ver>"`

Behavior:
- Computes ISO `(year, week, day_of_week)` from `local_date` and maps to existing Weekview toggle operation.
- Sets/clears the mark and returns 200 with new `ETag`.
- Returns 412 (ProblemDetails `etag_mismatch`) if `If-Match` doesn't match current ETag.
