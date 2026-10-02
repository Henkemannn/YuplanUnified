Status: LOCKED
Last reviewed: 2026-10-02

# Yuplan 1.0 Finishline

## Current Phase

Active phase: **Kommun 1.1 — Department Portal completion, then meal-path verification, tablet/iPad pass, and final fresh pilot smoke.**

The shared Builder/Menu seam is now closed for Yuplan 1.0. Shared Dish + Component editors are accepted as Yuplan 1.0-ready and must not be reopened for micro-polish before pilot unless a real blocker or regression is found.

The current focus is to finish the remaining Kommun operational path without broadening into Builder 1.1, Offshore expansion, Home, Hotel/Banquet, broad refactors, or new generic platform work.

## Current Local Development Checkpoint

Active local development branch:

`feat/planera-app-shell-2026-03-03`

Accepted local code checkpoint:

`bda732af9893b591856b658f034fc6a5f2580589`

`style(builder): finish shared dish and component editors`

At this checkpoint:
- worktree was clean
- focused Builder slice was 58/58 green
- live browser smoke was clean
- no JS/page/console/request errors
- no horizontal page overflow
- native modal scrollbars are visually hidden
- vertical overflow uses dynamic top/bottom fades
- Dish Overview horizontal Component rail remains independent and preserves left/right fade behavior
- Dish allergen presentation uses Swedish display labels
- Component header uses `KOMPONENT`
- Component visible description label is `Beskrivning`
- permanent success copy `Komponentdetaljer laddade.` is removed from normal idle state
- local `builder_library.db` cleanup was intentionally kept outside the source commit

Important repository state note:
- the GitHub remote development branch is behind the local development branch as of this documentation update
- this document records the **local accepted development truth**
- do not infer current code state from the remote development branch alone

## Shared Builder Editors — 1.0 Ready

The following are accepted for Yuplan 1.0:

### Dish editor
- same-page canonical shared editor
- tabs:
  - Översikt
  - Komponenter
  - Kalkyl
  - Allergener / kostinfo
- compact Component summary blocks / rail
- summary-first Dish Kalkyl with inline expandable Component detail
- one expanded calculation entry at a time
- shared calculation truth with Component editor
- Swedish allergen presentation names
- read-only allergen aggregation from linked Components
- hidden native vertical scrollbar + dynamic top/bottom fades
- horizontal Overview rail retains its own left/right overflow fades

### Component editor
- context-aware return behavior:
  - direct library -> Tillbaka till komponenter
  - opened from Dish -> Tillbaka till <dish>
- tabs:
  - Översikt
  - Recept & metod
  - Kalkyl
  - Allergener / kostinfo
- typography aligned with Dish / Yuplan system stack
- compact recipe and costing rows
- recipe-derived fields visually read-only in Kalkyl
- editable price fields remain primary costing inputs
- shared frontend calculation helper
- hidden native vertical scrollbar + dynamic top/bottom fades
- no nested horizontal row scrollbars at accepted desktop/tablet sizes
- current allergen editing retained and visually aligned
- visible user-facing language is Swedish

### Shared calculation seam
One frontend calculation truth is shared by Component and Dish.

Current supported behavior is preserved; do not introduce screen-specific formulas.

Future ingredient-specific conversion/density profiles must extend below or through this shared seam rather than create separate formulas per screen.

## Builder 1.1+ — Explicitly Deferred

Do not reopen these before Yuplan 1.0 pilot readiness unless a true blocker appears:

- full Builder Workspace redesign / authoring workspace IA
- canonical Ingredient Library
- reusable standard ingredient pricing
- price history / supplier article integration
- recipe ingredients automatically becoming costing rows
- exclude-from-costing on recipe rows
- additional costing-only rows
- organization/user conversion profiles
- ingredient-specific volume <-> weight conversions
- Recipe Import / Recipe Draft
- paste recipe text import
- document recipe import
- bulk recipe library import
- advanced Menu Builder drag-and-drop
- broader Builder workspace polish

Locked future direction:
- Builder is Yuplan's advanced authoring workspace
- daily operations should normally enter canonical editors from Kommun/Offshore flows
- Component -> Dish -> Menu remains the canonical Builder mental model
- recipes belong to Components
- published menu remains external/menu-facing truth

## Already Established Kommun Product Chain

Accepted operational chain:

Registered needs
-> varied quantity/current requirement truth
-> published canonical menu + department choices
-> Product2 Page1
-> Product2 Page2 review
-> Planera 2.0
-> Product2 Page3 Produktionsunderlag
-> mark complete
-> Kitchen Weekview
-> persistence
-> Admin Weekview
-> Reports

Key accepted principles:
- Builder is canonical menu knowledge source
- published menu projection drives Kommun menu options
- explicit department menu choice remains its own canonical truth
- missing choice must not silently become a fallback choice
- requirement groups represent disjoint recipient cohorts
- current quantities remain business truth
- Planera 2.0 Core remains generic
- Kommun adapters/presentation may add Kommun semantics without leaking them into Core
- specialkost primary/modifier semantics are explicit; they must not be guessed from display order
- completion/weekview persistence must remain operational truth, not visual-only state

## Current Active Gate — Department Portal

A Copilot implementation order has already been sent.

**Do not issue another implementation order until that report is returned and reviewed.**

Current gate goal:

Canonical Department Portal week surface at:

`GET /ui/portal/department/week`

The gate is intentionally small.

Required direction:
- route loads reliably in current Yuplan shell
- existing tenant/site/department scope is reused
- canonical published Builder menu is consumed
- existing department menu-choice truth is reused
- registered needs are read-only context where already supported
- no portal-specific shadow menu model
- no second department-choice model
- no broad portal redesign
- no old-route cleanup unless the report proves a tiny redirect is necessary and it is separately approved

Portal architecture remains:
- portals are experience/communication layers, not production engines
- Kommun Department Portal is a business-specific adapter over shared portal principles
- published/external menu truth comes from canonical publication
- the portal must not read private Cook/Work Menu state as external truth

## Remaining Path to Kommun 1.1 Pilot Ready

Strict sequence:

### 1. Department Portal
Review the currently outstanding Copilot report first.

Then, only if needed:
- one small follow-up portal gate at a time
- establish canonical week experience
- verify department choice behavior
- verify read-only registered-needs context
- verify route/auth/scope behavior
- tablet smoke

Do not pre-plan multiple portal gates before seeing the report.

### 2. Meal-path verification
Lunch is already proven.

Still verify the current Product2 path for:
- dinner/evening meal path
- dessert mapping where applicable
- no Kommun-only assumptions leaking into Planera 2.0 Core
- current published menu identity through the full path

This is verification-first, not redesign-first.

### 3. iPad / tablet acceptance
Priority sizes:
- 1024x768
- 768x1024

Check the real operational Kommun flow, not every page in the repository.

Focus on:
- no clipped controls
- usable touch targets
- no accidental horizontal page overflow
- readable production/portal tables
- stable shared editors when entered from Kommun

### 4. Final fresh pilot smoke
Must include:
- cold restart
- login repeatability
- canonical site/tenant context
- published menu
- department choices
- registered needs
- Page1 -> Page2 -> Planera 2.0 -> Page3
- completion/weekview persistence
- Department Portal
- report visibility where already in MVP scope
- browser/console/request cleanliness

### 5. Mark Kommun 1.1 PILOT READY
Only after the fresh smoke passes.

### 6. Controlled Planera transition
Run Planera 1 and Planera 2 side-by-side for real operational weeks.

Planera 1 remains a temporary fallback during transition.

Do not remove fallback until real-week parity is proven.

## Remaining Yuplan 1.0 Scope After Kommun

After Kommun 1.1 pilot readiness, return to the already scoped Offshore 1.0 work.

Do not mix Offshore completion into the current Department Portal / Kommun closure.

Yuplan 1.0 remains focused on:
- Kommun
- Offshore
- required shared canonical Builder foundations

Home and Hotel/Banquet remain outside Yuplan 1.0.

## Project Execution Rules

These rules are part of the finishline:

1. **One order -> one Copilot report -> review -> next order.**
2. Do not send a new implementation order while a report is outstanding.
3. Real browser evidence outranks DOM-contract confidence for UX acceptance.
4. Green focused tests do not replace live smoke.
5. Do not rewrite working functions without a specific reason.
6. Do not broaden a gate into cleanup/refactor work.
7. No speculative generic architecture during MVP closure.
8. Planera 2.0 Core stays generic.
9. No Builder modal micro-polish before pilot unless a real regression/blocker is proven.
10. Local accepted commit state is authoritative when the GitHub remote branch is behind.

## STOP Conditions

Stop and report before implementation if:
- active branch is wrong
- expected checkpoint differs
- unrelated dirty files exist
- the requested change requires a new source of business truth
- canonical menu/choice/requirement semantics are unclear
- a portal change would write production truth
- a change would require broad Builder or Planera 2.0 Core refactoring
- a migration would guess ambiguous business semantics

## Definition of Yuplan 1.0 Ready for Pilot

Yuplan 1.0 is ready for pilot when:
- Kommun 1.1 fresh pilot smoke is green
- Department Portal is usable and canonical
- meal paths required by the pilot are verified
- tablet/iPad operation is acceptable
- Planera 2.0 production truth remains authoritative and generic
- shared Builder editors remain stable
- Offshore 1.0 locked MVP scope is complete
- no pilot-blocking legacy dependency or duplicated source of truth remains
