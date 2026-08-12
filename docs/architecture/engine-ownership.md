# Engine Ownership Contract

This document is authoritative. Every future ticket must complete an ownership audit
before implementation begins.

---

## Builder Engine owns

- Components
- Component recipes and methods
- Component allergens
- Component calculations
- Dishes / Compositions
- Composition items
- Component roles and ordering
- Dish presentation and menu text
- Plating notes and images
- Menus
- Menu import and pipeline
- Canonical matching
- Aliases and unresolved resolution
- Publication
- Builder UI / editors — including the shared modal controllers

## Planera 2.0 Engine owns

- Normal meal baseline
- Dietary deviations and special diets
- Production quantities
- Destinations
- Prep, freezer pull, packing
- Production documentation
- Quantity logic and waste optimization
- Scaling and order projections

## Business Modules own (Offshore, Kommun, future)

- Site / installation / department context
- Rotations and schedules
- Workflow orchestration
- Local operational decisions

Business modules consume Builder and Planera through their published APIs and
shared UI components. They do not reimplement engine logic.

---

## Forbidden

The following are architecture violations that will be rejected at review:

- Copied Builder editors (Dish form, Component form)
- Copied Builder modals or modal controllers
- Parallel recipe engines
- Parallel Composition engines
- Module-specific canonical matching
- Copied Planera calculations
- Parallel special-diet logic
- Any "Light" variant of a Builder or Planera component

---

## Mandatory checklist before every future ticket

1. Ownership audit: which engine owns the domain touched by this ticket?
2. Identify the existing engine implementation (file, class, function).
3. Define the exact reuse path (API endpoint, shared JS, Jinja2 partial, Python module).
4. Define the adapter boundary: what is module-specific vs. engine-generic?
5. Explicit no-duplication confirmation: state clearly that no parallel implementation will be created.
