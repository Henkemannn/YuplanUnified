# MenuComponent – Menydetalj-ID för prepp/inköp/frys/recept

## Problem
Varje menyrad (per dag/måltid/variant/enhet) behöver ett stabilt `component_id` för att koppla på prepp, inköp, frysuttag och recept.

## Krav
- Stabilt per menydetalj över tid.
- Bundet till org/site/menu/day/meal/variant.
- Funktion som nav för:
  - prepp‑uppgifter
  - inköpsplaner
  - frysuttag
  - receptlänkar
  - telemetri

## Modellskiss (förslag)
```
MenuComponent(
  id,
  org_id,
  site_id,
  menu_id,
  day,         # ISO date
  meal,        # lunch | dinner
  variant,     # alt1 | alt2 | dessert | etc
  dish_id,     # koppling till rätt rätt/dish
  created_at,
  updated_at
)
```

### Relationer (förslag)
- PrepPlan(component_id, ...)
- PurchasePlan(component_id, ...)
- FreezerPlan(component_id, ...)
- RecipeLink(component_id, recipe_id, visibility, ...)

## API & VM integration (förslag)
- Weekview vm: injicera `component_id` per dag/måltid/variant i `days`/`menu_texts`‑strukturen.
- `/ui/planera/day` vm: exponera `component_id` per avdelning/måltid för korten och framtida moduler.
- Framtida endpoint: `/api/unified/menu-component/{component_id}` för att hämta/uppdatera kopplad metadata (flagga bakom FF i början).

## Next steps (ej implementerat än)
- Design review (ID‑stabilitet, variantdomän, koppling till dish).
- Migrationsplan (ny tabell + indexering på (site_id, day, meal, variant)).
- Experimental endpoint bakom feature flag.

Notera: Ingen kod ändras nu – detta är dokumentation som förankrar modell och integrationspunkter innan migrationsfasen.
