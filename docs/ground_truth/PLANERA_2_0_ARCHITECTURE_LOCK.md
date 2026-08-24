Status: LOCKED
Last reviewed: 2026-08-24

# Planera 2.0 Architecture Lock

## Purpose
Planera 2.0 is a generic production engine.
Core question: "What needs to be produced?"

## Preserved Principles
- context-neutral
- compute-first
- deterministic
- headless
- independently testable
- adapter-based
- no business-specific logic in templates or core
- small responsibility, strong structure

Builder is the Knowledge Source of Truth.
Planera consumes food knowledge; it does not duplicate it.

## Canonical Flow
Builder -> Components -> Dish -> Menu -> Published Menu
  -> Business Context / Effective Menu
  -> Demand
  -> Compatibility / Requirements
  -> Planning Slice / orchestration
  -> Planera 2.0 Core
  -> Production Requirement
  -> Operational / Intelligence layers

## Compatibility / Requirements
Builder knows food properties.
Example: Dish Kottbullar contains Components whose metadata may imply gluten and milk or lactose-related properties.

Business module knows recipient requirements.
Example: Department A has recipients requiring gluten-free, lactose-free, both, texture adaptations, etc.

The compatibility or application layer determines which demand can consume standard production and which demand requires a production variant.

Do not hardcode gluten, lactose, timbal, department, Alt1, Alt2, crew, shift, VIP, or similar business terms into Planera Core.
Those are adapter and application concepts.

## Planning Slice
A thin orchestration and input concept representing one actual service or Dish context plus demand and destinations that must be supplied.
It is not a new canonical persistence model or source of truth.
Do not create a parallel persistent Planning Slice database or domain unless a future locked decision explicitly requires it.

Planera Core input should remain generic around:
- baseline and demand
- units and destinations
- deviations, requirements, and variants
- context and references

## Production Requirement Traceability
Production Requirement must retain stable references or identity back to the context that produced it where available.
Examples of references may include service or event, menu or publication, Dish or composition_id, destination or unit, and business context identifiers.
These references exist for traceability and downstream consumers such as recipe scaling, prep, freezer, history, and analytics.
Planera does not take ownership of the referenced Builder or business objects.

Planera Core output must be capable of expressing:
- what production requirement the result belongs to
- quantity
- requirement or variant grouping
- destination and unit breakdown
- warnings

## Kommun First Use Case
- normalkost is the standard production baseline for the chosen Dish or menu option.
- department resident counts are demand.
- recipient dietary or texture requirements are business requirements.
- determine who cannot consume the standard production.
- Planera calculates normal quantity plus adapted production quantity and destination breakdown.

Example user-facing result:
Köttbullar:
87 standard portions.
2 gluten adaptations -> Department A.
3 lactose adaptations -> Departments B and C.
1 gluten plus lactose adaptation -> Department D.

Normalkost, specialkost, timbal, department, Alt1 and Alt2 are Kommun language, not Core language.

The current temporary form="specialkost" adapter fallback is not authoritative long-term form semantics and must not define Core.

## Future Capabilities Above Core
- recipe and yield scaling
- prep
- freezer pulls
- purchasing
- Husk att bestill
- packing and distribution
- planned vs produced vs consumed
- waste
- historical consumption
- forecasts
- analytics
- AI recommendations

Do not build those systems into Planera Core.

## Kommun Integration Strategy
- retain existing current production behavior initially.
- run Planera 2.0 in shadow mode from real Kommun input.
- use existing comparison and parity mechanisms.
- prove unit baselines, deviations, totals, and destinations.
- only switch production truth after parity is accepted.

## Offshore Later Use
Offshore later uses the same Planera Core through its own adapter: POB, shifts, visitors, crew requirements, and effective Work Menu.

## Absolute Rules
- no separate production engine per module.
- no Builder persistence inside Planera.
- no Kommun domain language hardcoded into core.
- no UI-driven domain redesign.
- no recipe, inventory, forecast, or AI system inside core.
- do not begin a large new Planera UI before architecture contracts are locked.
