# P0-D4: Planera v1.2 calm UX (progressive disclosure + work mode + meal-aware)

## Summary
- Adds step-based progressive disclosure: results render only with `show_results=1` (day+meal selected, user explicitly clicks "Visa tillagningslista").
- Adds "Vad planerar vi?" context block with week/day/meal.
- Adds "Arbetsläge" toggle: Specialkost vs Normalkost.
- Meal-aware normalkost table:
  - Lunch: Alt1/Alt2/Total
  - Dinner/Dessert: Normalkost/Total
- Keeps checklist visible and views mutually exclusive (calm, production-focused).
- Print remains via external CSS (CSP-safe), hides controls/toggles and prints only selected work mode.

## Scope
- Template/JS/CSS/tests changes; no changes to `PlaneraService`, `WeekviewService`, or database schema.
- Route-level viewmodel assembly only (exposing existing Planera data for the normalkost table) — no persistence or service logic changes.

## Tests
- `pytest -q -k kitchen_planering` → 10 passed, 2 skipped.

## Notes
- Progressive disclosure and meal-aware views align the kitchen planering page with production workflows.
- Results remain hidden until explicitly requested (`show_results=1`) to keep UI calm.
