# Yuplan Recipe & Knowledge Layer Architecture

## 🎯 Purpose

The **Yuplan Recipe & Knowledge Layer** is a structured knowledge system built on top of the core Yuplan engine (components, compositions, menus, and Planera 2.0).

Its purpose is to:

* Enable creation and reuse of structured recipes
* Connect recipes to components and menus
* Support production planning (yield, scaling, ingredients)
* Allow controlled sharing within and across tenants
* Provide a lightweight knowledge layer (not a social platform)

---

## 🧠 Core Principle

> **Workflow first, sharing second**

This is not a community feature.
It is a **production-aware knowledge system**.

---

## 🧱 Domain Model

### Recipe

Represents a structured recipe.

Fields:

* id
* tenant_id
* site_id (nullable)
* author_user_id
* title
* slug
* description
* instructions_markdown
* yield_portions
* prep_time_minutes (nullable)
* cook_time_minutes (nullable)
* visibility
* status
* source_type
* source_recipe_id (nullable)
* created_at
* updated_at
* published_at (nullable)
* archived_at (nullable)

---

### RecipeVisibility

Enum:

* private
* site
* org
* public (future)
* curated_public (future)

---

### RecipeStatus

* draft
* published
* archived
* flagged
* removed

---

### RecipeIngredient

* id
* recipe_id
* sort_order
* ingredient_name
* quantity
* unit
* note (nullable)
* optional (bool)

---

### RecipeComponentLink

Links a recipe to a component.

* id
* recipe_id
* component_id
* relation_type

Relation types:

* primary
* alternative
* default_for_component

---

## 🔁 Usage Model

### Recommended approach: **Fork / Snapshot**

When a recipe is used in a menu:

* A snapshot or version is created
* Production always uses a fixed version

This ensures:

* stability
* reproducibility
* historical traceability

---

## 🧬 Versioning

### RecipeVersion

* id
* recipe_id
* version_no
* title
* instructions_snapshot
* yield_portions
* created_by
* created_at
* change_note

---

## 🔐 Visibility & Access

All recipes must respect strict tenant boundaries.

### Levels:

* private → only creator
* site → same kitchen/site
* org → entire tenant
* public → global (future)

---

## ⭐ Social Layer (Lightweight)

Initial features:

### RecipeFavorite

* user_id
* recipe_id

### RecipeComment

* id
* recipe_id
* user_id
* body
* created_at

No feeds, no profiles in MVP.

---

## 🔍 Search & Discovery

Search must support:

* title
* ingredients
* tags
* component_id
* scope (private/site/org)

Ranking signals:

* usage frequency
* favorites
* recency
* component match

---

## 🔗 Integration with Planera 2.0

Flow:

1. Planera defines portion categories
2. Menu → Composition → Component
3. Component → Recipe (versioned)
4. Recipe → Ingredients
5. Output:

   * production list
   * prep list
   * purchase list

---

## 🖥️ UI Principles

The UI should feel like:

* a **professional library**
* a **knowledge system**

Not like:

* social feed
* forum

### Views

* Recipe Library (filters: Mine / Site / Org)
* Recipe Detail
* Attach Recipe to Component/Menu

---

## ⚠️ Risks & Mitigation

### Empty community

→ Seed with internal/curated recipes

### Low quality

→ visibility control + moderation

### Tenant leakage

→ strict filtering

### Social noise

→ keep social layer minimal

---

## 🧭 Development Phases

### Phase A — Foundation

* Recipe model
* Visibility
* Basic search

### Phase B — Workflow Integration

* Attach recipe to component
* Use recipe in menu
* Snapshot logic

### Phase C — Production

* Yield scaling
* Planera integration

### Phase D — Light Social

* Favorites
* Comments

### Phase E — Shared Layer

* curated_public
* recommendations

---

## 🚀 MVP Recommendation

### MVP 1

* Create recipe
* Visibility: private/site/org
* Attach to component
* Basic search
* Favorites

### MVP 2

* Use recipe in menu
* Snapshot/fork
* Comments

### MVP 3

* Public recipes
* Recommendations

---

## 🧠 Final Positioning

This is not a community module.

It is:

> **A production-grade knowledge layer for structured kitchen data**

It must always:

* support real workflows
* integrate with planning
* enable accurate production

---

## ✅ Summary

* Built on top of component/composition system
* Structured, not free-text
* Tenant-safe
* Workflow-integrated
* Social features are secondary

---

End of document
