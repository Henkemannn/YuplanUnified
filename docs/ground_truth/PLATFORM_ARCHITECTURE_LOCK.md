Status: LOCKED
Last reviewed: 2026-08-22

# Platform Architecture Lock

## Knowledge Layer
- Builder.
- Components -> Dishes/Compositions -> Menus.
- Recipes and recipe data belong to Components.
- Builder describes what the food is.

## Publication
- Published Menu is the immutable business baseline.

## Business / Application Layer
- Kommun / Offshore / future Hotel / Bankett / Catering.
- Owns business context: when, where, for whom, menu choices, departments, POB, crew, local operational choices, dietary and customer requirements.

## Effective Business Context
- The actually applicable Dish or menu identity for the current actor or business situation.
- Published menu stays baseline.
- Operational or private choices do not mutate publication.

## Production Layer
- Planera 2.0.
- Transforms effective demand into production requirements.
- Describes what needs to be produced.

## Intelligence / Operational Layer
- Recipe scaling, prep, freezer, purchasing, history, waste, forecasting, analytics, AI.
- Built above Planera.
- Describes how to produce smarter.

## Portals
- Experience and communication layer.
- Consume platform truth.
- Do not become parallel menu or production truth.

## Dependency Direction
Builder -> Publication -> Business Context / Effective Demand -> Planera 2.0 -> Production Output -> Operational / Intelligence.

No reverse ownership.
