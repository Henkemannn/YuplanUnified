# Allergen Display Codes (Architecture Note)

Status: architecture note only (no runtime behavior change)

## Purpose
This note defines a future-ready display-code mapping for EU14 allergens used in menus, print exports, and planning views.

Current source of truth remains the stable allergen keys stored on component data.

## Scope and non-goals
- Stable allergen keys remain canonical for storage and logic.
- Display codes are presentation metadata only.
- This note does not change save payloads, backend persistence, checkbox behavior, menu rendering, or component pills.

## Stable EU14 key to display code mapping

| Stable key | Swedish label | Display code |
|---|---|---|
| gluten_cereals | Glutenhaltiga spannmal | G |
| crustaceans | Kraftdjur | K |
| eggs | Agg | A |
| fish | Fisk | F |
| peanuts | Jordnotter | J |
| soybeans | Sojabonor | S |
| milk_lactose | Mjolk/laktos | M |
| nuts | Notter | N |
| celery | Selleri | C |
| mustard | Senap | SE |
| sesame | Sesamfron | SF |
| sulphur_dioxide_sulphites | Svaveldioxid och sulfiter | SO |
| lupin | Lupin | L |
| molluscs | Blotdjur | B |

Note: labels above are intentionally plain ASCII in this document file to avoid encoding issues. UI labels continue using Swedish diacritics where implemented.

## Presentation guidance for future views
- Use compact code badges for dense surfaces (menus, print blocks, plan grids).
- Include a legend near the output so codes can be decoded quickly.
- Avoid emoji-only meaning in safety contexts because print/device rendering is inconsistent.

Possible display modes:
- Code badges (default recommendation)
- Optional icon plus code
- Numbered legend linked to code badges

## Implementation guidance for future work
- Keep storage and API payloads key-based.
- Resolve key to display metadata at render time.
- If a central frontend allergen metadata constant is introduced later, it should include:
  - stable key
  - Swedish label
  - display_code
  - optional icon token
- Unknown keys should degrade gracefully (show full label or raw key, never drop data silently).
