Status: LOCKED
Last reviewed: 2026-08-27

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

## Tenant and Ownership Boundary
- Tenant isolation is a platform invariant, not a UI concern.
- organisation-scoped canonical data may be shared inside one tenant only.
- user/private data is isolated to the owning actor according to the scope rules.
- Business modules must pass real actor/tenant context into scope-aware canonical writes.
- No production path may fabricate a principal or borrow a user from another tenant merely to satisfy scope.
- Legacy objects without scope are compatibility debt and must not define the architecture for new tenants.

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
