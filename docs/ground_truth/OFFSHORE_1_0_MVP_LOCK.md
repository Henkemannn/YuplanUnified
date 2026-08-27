Status: LOCKED
Last reviewed: 2026-08-27

# Offshore 1.0 MVP Lock

## Goal
Offshore 1.0 must let a new installation be provisioned and operated without developer scripts or duplicate Builder data models. It should be pilot-ready for a real offshore kitchen while staying deliberately smaller than the long-term Offshore product.

## Three Pillars

### A. Provisioning
Primary setup flow:
Installation -> Menu Cycle -> Rotation/Turnus Template -> Virtual Crew Slots -> Staffing -> Review -> Activate.

- Provision from Kommandobryggan / central administration.
- Reuse existing Offshore domain objects instead of introducing parallel setup tables.
- Site administration may later manage substitutions and local staffing changes.
- Setup must establish correct tenant/site ownership from the first canonical write.
- Provisioning/seed flows must use a real principal belonging to the target tenant; fabricated or borrowed cross-tenant principals are forbidden.

### B. Cook Operations
Primary cook flow:
Current Rotation -> Work Menu -> Ändra rätt -> Prep -> Frysplock -> Husk att bestill.

- Published menu is the immutable baseline.
- Work Menu is the cook's effective operational view.
- A cook may choose or create a real canonical Builder Dish through the shared Builder runtime.
- Personal COW/Work Menu state belongs to that user and must not overwrite another cook or the shared source.
- A substitute receives the applicable baseline plus their own private operational state, not the predecessor's private state.
- Simple prep, freezer-pick and order-reminder support are MVP; advanced optimization is not.

### C. Crew Experience
Mässportal uses the shared Portal Foundation where practical.

MVP surface:
- published menu
- allergens / food information
- meal times
- practical crew information
- responsive/iPad-friendly presentation

The portal does not own menu or production truth.

## Canonical Offshore Structure
Preferred direction:
Installation -> Menu Cycle -> Rotation Template -> Virtual Crew Slots -> Rotation Occurrence / Work Period -> User Assignment -> Effective Work Period -> Personal Work Menu -> Planera/Prep/Freezer.

- Virtual Crew Slot owns schedule identity.
- User owns private Work Menu/COW state.
- Existing legacy turnus implementation is reference material, not automatically canonical architecture.

## Builder and Planera Boundaries
- Builder owns Components, Dishes/Compositions, Menus and food knowledge.
- Offshore owns installation, rotation, POB/crew, assignment and operational context.
- Planera 2.0 owns production calculation.
- Offshore must not create a second Dish/Component library or production engine.

## Integration Principle
Integrate first, build own only where Yuplan creates unique value.

Examples:
- Weather/marine information may come from external providers via an adapter based on installation coordinates.
- Normalize external data before portal use.
- Show provider/source and last update.
- Do not claim certified navigation/safety status unless the integrated source/product explicitly supports it.

Weather/marine is useful pilot/post-pilot experience but is not a launch blocker for Offshore 1.0.

## Not 1.0 Blockers
- advanced AI forecasting
- advanced waste optimization
- full inventory/purchasing engine
- advanced consumption analytics
- H3 Offshore Bibliotek as a separate product surface
- certified marine/navigation tooling
- broad reporting suites

These may be built later on top of the canonical Builder -> Business Context -> Planera architecture.
