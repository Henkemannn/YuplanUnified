Status: LOCKED
Last reviewed: 2026-08-24

# Builder Menu Lock

- Builder owns Components, Dishes/Compositions, and Menus.
- Components own recipe, costing, notes, allergens, and food metadata.
- Dishes compose Components.
- Dishes do not own recipes.
- Menu rows carry canonical composition_id when resolved.
- unresolved or free text is fallback, not the preferred canonical identity.
- composition_name = internal, work, or library Dish name.
- use_custom_menu_name is a boolean that controls custom menu presentation.
- menu_name is optional presentation name.
- effective_menu_name:
  - custom enabled + non-empty menu_name => menu_name
  - otherwise composition_name.
- Work Menu uses the actor or cook scoped effective composition_name.
- Published menus, portals, print/menu presentation, and other external menu-facing surfaces SHALL use effective_menu_name.
- A cook's private Work Menu or COW identity must never leak into published or external menu presentation unless that operational choice is explicitly promoted or published through the proper publication flow.
- published menu remains the immutable baseline.
- Cook private COW must never alter Land, Admin, shared source, or another Cook.
- Offshore does not create duplicate Dish or Component libraries or editors.
- canonical standalone Builder editors are reused by business modules.
- Builder is not a production engine.
