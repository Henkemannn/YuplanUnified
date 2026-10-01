# Yuplan Builder Future Lab — Recipe Import, Component Matching & Unit Normalization

**Status:** Future Lab / product-direction lock  
**Target:** Builder 1.1, with bulk-library expansion in Builder 1.2  
**Date:** 2026-10-01  
**Scope:** Builder / Components / Recipes / Import / Calculation foundation

---

## 1. Product intent

Yuplan should make it dramatically easier for a professional kitchen to bring existing recipe knowledge into the platform.

The user should not need to manually recreate years of recipes before Yuplan becomes useful.

A recipe can arrive as:

- pasted plain text
- a single uploaded document
- later, a folder / ZIP / batch of recipe documents
- eventually other source types such as PDF, image, web source or scanned recipe card

The important product principle is that these are all different **input sources**, not different product architectures.

They should feed the same import pipeline.

---

## 2. Core domain principle

Yuplan keeps the existing composable hierarchy:

```
Component
  -> Dish
    -> Menu
```

A recipe belongs to a **Component**.

A Dish composes Components.

A Menu composes Dishes.

Therefore:

> importing a recipe should result in a Recipe Draft that is attached to an existing Component or used to create a new Component.

A user should not have to understand Yuplan's internal Component model before importing a recipe.

The user thinks:

> "I want to import my recipe for bearnaise."

Yuplan should handle the Component decision as part of the import flow.

---

## 3. One importer, several detected content types

The long-term UX should be one primary action:

# Importera

The user can:

- paste text
- drag in a file
- choose a file
- later select/drop multiple files

Yuplan analyses the content and proposes what it appears to be.

Example:

> **Recept identifierat**  
> Morotskaka  
> 13 ingredienser · 8 metodsteg · 12 portioner

The user can confirm or override the interpretation.

Recommended primary content types:

### Menu

Example:

```
Måndag
Lunch: Köttbullar med potatismos
Kväll: Korv Stroganoff

Tisdag
...
```

This goes through Yuplan's Menu Import flow and resolves Dishes / unresolved menu rows.

### Dish

A structured or free-text description of a composed dish can be interpreted as a Dish and matched against Components where appropriate.

### Recipe

Ingredients + amounts + units + method.

A Recipe import always continues into:

```
Recipe Draft
-> match/create Component
-> review
-> approve
-> save
```

### Important UX decision

Do **not** make "Component" a normal equal top-level import choice next to Menu / Dish / Recipe.

Component is primarily Yuplan's internal reusable building object.

For normal kitchen users the more natural intent is:

- import a menu
- import a dish
- import a recipe

Structured Component/CSV import can be an advanced future capability if needed.

---

## 4. Recipe import flow

Example input:

```
Köttbullar

500 g blandfärs
1 dl mjölk
1 dl ströbröd
1 ägg
1 tsk salt

Blanda ströbröd och mjölk...
Forma köttbullar...
Stek...
```

Yuplan parses into a Recipe Draft:

- title
- ingredient rows
- amount
- unit
- ingredient text
- method / steps
- servings / batch size when available
- source/original text
- parse confidence / unresolved fields where useful

The import must then perform Component matching.

---

## 5. Existing Component matching

If the recipe title resembles an existing Component, Yuplan should not silently create a duplicate and must never overwrite an existing Component automatically.

Example:

Imported recipe:

> Köttbullar

Existing library contains:

> Köttbullar

Yuplan should present:

> **En liknande komponent finns redan: Köttbullar**

Actions:

1. **Lägg receptet till befintliga Köttbullar**
2. **Skapa ny komponent**
3. **Välj annan komponent**

If creating a new Component, the user can name it freely, for example:

- Julköttbullar
- Mammas köttbullar
- Köttbullar — klassisk
- Köttbullar catering
- any user-defined name

Suggested naming is allowed, but the user owns the final name.

---

## 6. Matching and aliases

The matching model should build on the same conceptual pattern already used by Builder/Menu import:

- normalized names
- aliases
- fuzzy matching
- unresolved review
- explicit user confirmation

Example:

Imported title:

> Mammas köttbullar

User maps it to:

> Köttbullar

Yuplan may then remember that alias for future imports.

Important:

- fuzzy match is a suggestion
- high similarity does not mean automatic overwrite
- user confirmation remains authoritative

---

## 7. Paste recipe text — Builder 1.1 candidate

A high-value first implementation should support a very low-friction workflow:

1. Open Importera
2. Paste copied recipe text
3. Yuplan detects Recipe
4. Parse title / ingredients / method
5. Show Recipe Draft
6. Match against existing Components
7. User selects existing Component or creates new one
8. Review
9. Save

This means a chef can:

- find a recipe online
- copy the text
- paste it into Yuplan
- turn it into structured reusable Yuplan data

without manually retyping each field.

This is a strong Builder 1.1 capability.

---

## 8. Single document import — Builder 1.1 candidate

The same pipeline should support one uploaded recipe document.

Initial useful formats can include:

- .docx
- .txt
- PDF when extraction quality is reliable

The file layer extracts text and passes it to the same Recipe Draft parser.

Avoid building separate business logic for:

- Word import
- pasted-text import
- PDF import

The architecture should instead be:

```
SOURCE ADAPTER
-> TEXT / STRUCTURED EXTRACTION
-> RECIPE PARSER
-> NORMALIZATION
-> COMPONENT MATCH
-> REVIEW
-> SAVE
```

---

## 9. Recipe library import — Builder 1.2 candidate

Many professional cooks have years of recipes stored as:

- Word files
- PDFs
- text files
- folders on a laptop
- phone/cloud folders
- exports from older systems

Yuplan should eventually support importing many recipe files as one job.

Example onboarding result:

> **187 recept identifierade**
>
> 143 nya Components föreslås  
> 31 matchar befintliga Components  
> 13 behöver granskas

The user should work through a review queue rather than open 187 independent dialogs.

Useful states:

- Ready to import
- Existing Component match
- Possible duplicate
- Needs review
- Could not parse

This should be treated as a separate Builder 1.2-scale capability because batch import introduces:

- duplicate handling
- partial failures
- queue/review UX
- conflict handling
- progress/status
- bulk approval

The single-recipe architecture in Builder 1.1 must be designed so bulk import can reuse it later.

---

## 10. Preserve the original source

Yuplan must never destroy the imported source representation.

Example source:

> 5 dl vetemjöl

Even if Yuplan later normalizes this to:

> approximately 300 g vetemjöl

the original value should remain available.

Recommended principle:

```
original source
+
parsed structured value
+
normalized value
```

The parsed/normalized representation may improve over time without losing what the user originally imported.

This is important for:

- trust
- review
- correcting parser mistakes
- future conversion changes
- auditability

---

## 11. Unit normalization

Recipe import and costing should ultimately share one unit/conversion foundation.

Yuplan needs to distinguish three categories.

### A. Same-dimension conversions

These can be deterministic.

Examples:

- g <-> kg
- ml <-> cl <-> dl <-> l

### B. Kitchen measure to volume

Examples:

- tsp / tsk -> ml
- tbsp / msk -> ml
- dl -> ml

These are also deterministic when the measure definition is known.

### C. Volume to mass

Examples:

- dl flour -> g
- dl sugar -> g
- tbsp butter -> g
- dl syrup -> g

These are **ingredient-dependent**.

1 dl flour does not weigh the same as 1 dl sugar.

Therefore volume-to-mass conversion requires ingredient-specific conversion metadata such as a density / kitchen conversion profile.

---

## 12. Ingredient conversion profiles

Future Ingredient Library data can support normalized conversion metadata.

Conceptually:

```
Ingredient: Vetemjöl
source quantity: 5 dl
normalized volume: 500 ml
ingredient conversion profile: vetemjöl
normalized mass: approx X g
```

The exact data model is not locked by this document.

The important architecture requirement is:

> Do not design the current calculation engine so narrowly that it assumes every quantity is already grams and every price basis is kr/kg.

---

## 13. Display modes

A normalized recipe should later be able to support different useful representations.

Example original:

> 5 dl vetemjöl

Possible Yuplan views:

### Original recipe

> 5 dl vetemjöl

### Weight-oriented kitchen view

> ca 300 g vetemjöl

### Scaled production view

> 3.0 kg vetemjöl

### Costing view

> normalized quantity x product price basis

The source does not change; the presentation and normalized working quantity can.

---

## 14. One calculation truth

This is a critical architecture constraint.

Do not create independent formulas in:

- Component editor
- Dish editor
- Recipe import
- Planera
- purchasing

Instead, these consumers should ultimately share one canonical quantity/cost conversion layer.

Conceptual input:

```
ingredient
quantity
source_unit
price_value
price_basis_unit
conversion metadata
```

Conceptual result:

```
normalized quantity
normalized unit
calculated cost
conversion metadata / confidence where relevant
```

This does not require implementing the full future engine during Builder 1.0.

It does require avoiding short-term helpers that hard-code assumptions such as only:

```
grams + kr/kg
```

---

## 15. Connection to current Builder objects

The target lifecycle becomes:

```
Imported source
      |
      v
Recipe Draft
      |
      +--> parse ingredients
      +--> parse quantities / units
      +--> parse method
      +--> preserve source
      |
      v
Component Match
      |
      +--> attach to existing Component
      |
      or
      |
      +--> create new Component
      |
      v
Component
      |
      +--> Recipe & method
      +--> Calculation
      +--> Allergens / food info
      +--> future normalized ingredient data
      |
      v
Dish
      |
      v
Menu
      |
      v
Planera / production / purchasing
```

---

## 16. Why this matters for Yuplan

This is more than a convenience feature.

It can become a major onboarding advantage.

A professional chef may already have a large personal or organizational recipe library.

Without import:

> "Before Yuplan becomes useful I need to manually rebuild all my recipes."

With Yuplan Recipe Import:

> "Bring your recipe library with you."

Once imported and structured, the same information can power:

- Components
- Dishes
- menus
- recipe scaling
- costing
- allergens
- production quantities
- purchasing
- future stock/order workflows
- Planera

Import therefore becomes an entry point into Yuplan's structured operational model.

---

## 17. Suggested roadmap

### Yuplan 1.0 / current MVP

Do not broaden the current pilot into full AI recipe import.

Focus remains on:

- stable Builder Component/Dish foundations
- Kommun
- Offshore
- pilot readiness

### Builder 1.1

Candidate scope:

- unified Importera entry point
- pasted recipe text
- single recipe document upload
- auto-detect Recipe
- Recipe Draft preview
- title/ingredients/method parsing
- preserve source text
- match existing Component
- attach to existing Component
- create new Component
- explicit duplicate confirmation
- initial unit normalization foundation

### Builder 1.2

Candidate scope:

- folder / multi-file / ZIP recipe-library import
- import queue
- duplicate/match review
- partial failure handling
- bulk approval
- richer document support
- stronger ingredient conversion profiles

### Later

Possible extensions:

- scanned recipes
- photographed recipe cards
- handwritten sources when reliable
- direct URL/web-source ingestion
- richer ingredient knowledge
- learned organization-specific aliases
- recipe variants/versioning

---

## 18. UX guardrails

1. Never silently overwrite an existing Component.
2. Never silently merge two recipes only because names are similar.
3. Preserve the original imported source.
4. Show unresolved parser results for review.
5. Let the user override Yuplan's detected content type.
6. Prefer normal kitchen language over internal domain terminology.
7. Reuse one import pipeline rather than separate implementations per file type.
8. Reuse one calculation/conversion truth rather than recreating math per screen.
9. Treat AI/parser output as a draft until the user approves it.
10. Keep single-recipe import simple enough that paste -> review -> save feels fast.

---

## 19. Example end-to-end flows

### A. New Morotskaka recipe

User pastes recipe text.

Yuplan:

> Recept identifierat: Morotskaka  
> 13 ingredienser · 8 metodsteg

No close Component exists.

Action:

> Skapa Component "Morotskaka"

User reviews and saves.

Result:

```
Component: Morotskaka
  -> Recipe & method
  -> Calculation
  -> Allergens
```

### B. Köttbullar matches existing Component

User imports a recipe named Köttbullar.

Yuplan finds:

> Existing Component: Köttbullar

User chooses:

> Lägg receptet till befintliga Köttbullar

No duplicate Component is created.

### C. Recipe should become a variant

User imports:

> Julköttbullar

Yuplan suggests existing:

> Köttbullar

User instead chooses:

> Skapa ny Component

and names it:

> Julköttbullar

Both Components remain reusable and distinct.

### D. Existing Word recipe library

User later imports a folder of recipe documents.

Yuplan extracts each source through source adapters, creates Recipe Drafts and sends them through the same parser/matcher used for single imports.

Only exceptions require manual intervention.

---

## 20. Architecture lock from this concept

The following product principles should be treated as the important takeaway for future implementation:

**One importer, multiple source adapters.**

**Auto-detect content type, but let the user override it.**

**Recipe import resolves to an existing or new Component.**

**Do not expose Component as a confusing primary import choice for normal recipe users.**

**Preserve original source alongside structured/normalized data.**

**Unit normalization must distinguish exact unit conversion from ingredient-specific volume-to-weight conversion.**

**Calculation and unit conversion must move toward one reusable truth shared by Component, Dish, import and later production/purchasing.**

**Single-recipe import belongs in Builder 1.1; bulk recipe-library onboarding is a natural Builder 1.2 expansion.**
