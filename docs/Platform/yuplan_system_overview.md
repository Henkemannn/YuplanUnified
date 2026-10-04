# Yuplan System Overview

## Purpose

This document is the top-level system map for Yuplan.

It preserves the architectural separation between the Library Layer, the Menu Context Layer, and the Production Layer while reflecting the current October 2026 implementation truth.

## Core Architecture

Yuplan still consists of three primary layers.

### 1. Library Layer (Builder / Knowledge)

This layer defines what things are.

Current truth:

- Components and Compositions are the canonical library objects.
- Menu import works.
- The shared Dish editor is accepted.
- The shared Component editor is accepted.
- Recipe/method belongs to the Component editor.
- Unresolved/import/alias workflows exist and are part of the live system.
- The canonical published Builder menu is the downstream menu truth.

Related docs:

- component_model_v1.md
- component_composition_architecture.md
- component_recipe_architecture.md
- recipe_knowledge_layer_architecture.md

### 2. Menu Context Layer

This layer defines where and how library objects are used.

Menus are not limited to weekly schedules.

Supported contexts still include:

- weekly
- event
- catering
- à la carte
- proposal
- freeform

Related docs:

- menu_context_architecture.md
- menu_component_architecture.md
- menu_composition_integration.md
- eventcase_domain_architecture.md

### 3. Production Layer (Planera 2.0)

This layer defines what must be produced.

Planera 2.0 is not a future-only concept. The core engine is substantially built and already exercised in current flows.

Current truth:

- The core engine exists and is used.
- The Kommun adapter/integration exists.
- The canonical requirement-group flow exists.
- The Product2 Page1/Page2/Page3 flow has been exercised.
- Production-underlag exists.
- Planera 2.0 remains the production engine, not a menu system.

## Planera 2.0 Core Model

The fundamental model remains:

Demand → Categories → Production

Baseline demand is the total number of portions required.

Categories are the dynamic production divisions applied to that demand, such as normal, veg, special, VIP, or other context-specific variants.

Production output is the operational result: portions per category, production grouping, and the path to ingredient needs, prep lists, and purchasing.

The system must think in terms of demand division into production categories, not in terms of who cannot eat the main dish.

The same engine is intended to work across municipality, offshore, catering, restaurant, and events.

Related docs:

- planera2_motor_flow.md
- planera2_architecture.md
- ingredient_purchasing_architecture.md

## Data Flow

Menu Row → Composition → Components → Recipe → Yield → Production

## Builder Status

Builder is currently responsible for importing menus, creating compositions, building components, and learning via alias.

Current capabilities include:

- unresolved → create + build
- auto-suggest components
- rename / remove
- Swedish character support
- alias learning
- improved UX

## AI / Automation

AI is not part of the core logic.

It may assist, suggest, and learn patterns, but deterministic logic remains the base.

Related docs:

- planera2_ai.md
- ai_data_truth_principles.md

## Extended Domains

Yuplan is still designed to expand into:

- Event / Banquet
- Purchasing
- Portals

## Design Principles

- Library is not planning.
- Menu is not production.
- Demand drives everything.
- Categories are dynamic.
- There is no hardcoded weekly thinking.
- UX must stay simple.
- Backend must stay clean.

## Current Development Order

### KOMMUN 1.1

- Automated technical gate is GO.
- Clean-customer live acceptance is pending.
- UI/UX race is pending.
- Only blocker/high-impact fixes should be taken before release candidate freeze.

### Current next step

- Live customer-from-zero acceptance.
- UI/UX race.
- Release candidate freeze/tag.

### After Kommun 1.1

- Offshore 1.0.

### After that

- Broader recipe/yield/ingredient purchasing work.
- Hotel/Bankett/Event.
- Other platform expansion.

## Test Status

Current automated truth:

- 2342 passed
- 15 skipped
- 0 failed
- 3 warnings

This is the current clean baseline.

## Performance Note

TEST-PERF-1:

Offshore demo-seed tests consume about 226.8 seconds, or about 42% of the full test runtime.

That is a high optimization opportunity, but it is not a Kommun pilot blocker.

## Final Note

This document is the system truth.

If something conflicts with it, this document wins.