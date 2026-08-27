Status: LOCKED
Last reviewed: 2026-08-27

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
- Cook private COW must never alter Land, Admin, shared source, another Cook, or another tenant.
- Offshore does not create duplicate Dish or Component libraries or editors.
- Canonical standalone Builder editors and the shared Builder Component Library runtime are reused by business modules.
- Embedded hosts may isolate shell/CSS/return behavior, but must remain thin and must not become shadow Builder runtimes.
- Builder is not a production engine.

## Scope Integrity
- Canonical Builder objects are tenant/user scoped platform data.
- organisation scope may be shared only inside the same tenant.
- user/private scope follows the owning actor and is the basis for private Cook COW.
- A scope-aware canonical create must never silently create an unscoped Component or Composition.
- Missing-scope legacy objects are compatibility debt, not a valid canonical product scope.
- Legacy scope repair must not guess tenant ownership. Provenance is required before backfill.
- Missing-scope read compatibility may remain temporarily while legacy data is migrated.
- Target state after migration/parity is missing-scope deny-by-default.
