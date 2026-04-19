# Yuplan System Overview

## 🎯 Purpose

This document is the top-level system map for Yuplan.

It connects all architecture documents and ensures that:

- the platform stays broad
- Planera 2.0 is correctly understood as a production engine
- Builder, Menu Context, and Production are not mixed together

This is the entry point for understanding the system.

---

# 🧱 CORE ARCHITECTURE

Yuplan consists of three primary layers:

## 1. Library Layer (Builder / Knowledge)

Defines what things are.

- Components
- Compositions (dishes)
- Recipes
- Ingredient structures
- Knowledge sharing

📄 Related docs:
- component_model_v1.md
- component_composition_architecture.md
- component_recipe_architecture.md
- recipe_knowledge_layer_architecture.md

---

## 2. Menu Context Layer

Defines where and how things are used.

Menus are NOT limited to weekly schedules.

Supported contexts:

- weekly
- event
- catering
- à la carte
- proposal
- freeform

📄 Related docs:
- menu_context_architecture.md
- menu_component_architecture.md
- menu_composition_integration.md
- eventcase_domain_architecture.md

---

## 3. Production Layer (Planera 2.0)

Defines what must be produced.

Planera 2.0 is a production engine, not a menu system.

---

# 🧠 PLANERA 2.0 – CORE MODEL

## 🔁 Fundamental Model

Demand → Categories → Production

---

## 🧩 Definitions

### Baseline (Demand)

Total number of portions required.

Examples:
- 120 residents
- 80 crew
- 200 guests

---

### Categories / Variants

How demand is divided.

Examples:
- normal
- veg
- special
- VIP
- crew_day / crew_night
- allergen variants

These are:
- dynamic
- context-dependent
- not hardcoded

---

### Production Output

What the system produces:

- portions per category
- production grouping
- later:
  - ingredient needs
  - prep lists
  - purchasing

---

## 🚨 Important Principle

The system must NOT think:

“who cannot eat the main dish?”

It must think:

👉 “how must demand be divided into production categories?”

---

## 🌍 Context Neutrality

The same engine must work for:

- municipality
- offshore
- catering
- restaurant
- events

---

# 🔗 DATA FLOW

Menu Row  
→ Composition  
→ Components  
→ Recipe  
→ Yield  
→ Production  

📄 Related docs:
- planera2_motor_flow.md
- planera2_architecture.md
- ingredient_purchasing_architecture.md

---

# 🛠 BUILDER (CURRENT STATE)

Builder is responsible for:

- importing menus
- creating compositions
- building components
- learning via alias

Current capabilities:

- unresolved → create + build
- auto-suggest components
- rename / remove
- Swedish character support
- alias learning
- improved UX

---

# 🧠 AI / AUTOMATION (FUTURE)

AI is NOT part of the core logic.

AI will:
- assist
- suggest
- learn patterns

But:

👉 deterministic logic is always the base

📄 Related docs:
- planera2_ai.md
- ai_data_truth_principles.md

---

# 🧩 EXTENDED DOMAINS

Yuplan is designed to expand into:

## Event / Banquet
- eventcase_domain_architecture.md

## Purchasing
- ingredient_purchasing_architecture.md

## Portals
- crew_portal_architecture.md
- department_portal_architecture.md

---

# 🧭 DESIGN PRINCIPLES

- Library ≠ Planning
- Menu ≠ Production
- Demand drives everything
- Categories are dynamic
- No hardcoded “weekly thinking”
- UX must be simple
- Backend must stay clean

---

# 🚀 DEVELOPMENT ORDER

## Phase 1 (current)
Builder stable ✔

## Phase 2
Library mode (free creation)

## Phase 3
Planera 2.0 integration

## Phase 4
Recipe + yield + ingredient calculation

## Phase 5
Purchasing + prep + production optimization

---

# 💬 FINAL NOTE

This document replaces the need to rely on chat history.

If something conflicts:
👉 this document wins

If something is unclear:
👉 update this document

This is the system truth.