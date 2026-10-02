# KOMMUN 1.1 HARD HANDOFF — 2026-10-02

Status: ACTIVE HANDOFF  
Purpose: start a new ChatGPT project-management thread without losing project state  
Development branch: `feat/planera-app-shell-2026-03-03`  
Documentation branch only: `handoff/kommun-1-1-2026-10-02`

> **DO NOT DEVELOP ON THIS HANDOFF BRANCH.**
>
> The handoff branch exists only so the next chat can read the current project truth from GitHub.
> Development continues locally on `feat/planera-app-shell-2026-03-03`.

---

# 1. FIRST INSTRUCTION TO THE NEXT CHAT

Act as project manager / technical lead for Yuplan Unified.

The user is driving the product and GitHub Copilot in VS Code performs most implementation work.

Your job is to:
- keep the project coherent
- choose the next smallest safe gate
- write precise Copilot orders
- review each Copilot report before any new order
- protect accepted architecture and product decisions
- prevent scope creep
- prioritize real browser UX evidence and pilot readiness

## Non-negotiable workflow

**ONE ORDER -> ONE COPILOT REPORT -> REVIEW -> NEXT ORDER**

Never send another implementation order while a Copilot report is outstanding.

If a report is outstanding when this chat starts, review that report first.

---

# 2. CRITICAL REPOSITORY STATE

## Active local development branch

`feat/planera-app-shell-2026-03-03`

## Accepted local code checkpoint

`bda732af9893b591856b658f034fc6a5f2580589`

`style(builder): finish shared dish and component editors`

At this checkpoint:
- worktree clean
- focused Builder slice: 58/58 passed
- live browser smoke clean
- no JS/page/console/request errors
- no horizontal page overflow
- source checkpoint excluded local `builder_library.db`

## IMPORTANT: REMOTE DEVELOPMENT BRANCH IS STALE

At handoff creation time, GitHub remote:

`feat/planera-app-shell-2026-03-03`

was still at:

`97e4189614d51d020ed0284bd563a961ea286f29`

Therefore:

**DO NOT use GitHub remote HEAD as the current code checkpoint.**

The local VS Code/Copilot working tree is ahead.

When the next Copilot report arrives, use local commands as truth:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

Expected local HEAD before the current Department Portal gate:

`bda732af9893b591856b658f034fc6a5f2580589`

---

# 3. CURRENT STATE AT CHAT SWITCH

The shared Builder modal pass is FINISHED.

Milestone:

**Shared Dish + Component editors = Yuplan 1.0-ready**

Do not reopen for micro-polish before pilot unless a real bug/regression/blocker is demonstrated.

Immediately before this handoff, the user sent the first Department Portal implementation order to Copilot.

## CURRENT ACTIVE GATE

**Kommun 1.1 — Department Portal — Implementation Gate 1**

The order has already been sent.

### HARD RULE

**WAIT FOR THE COPILOT REPORT.**

Do not send another order in the new chat before that report has been pasted and reviewed.

---

# 4. CURRENT DEPARTMENT PORTAL GATE

Canonical route:

`GET /ui/portal/department/week`

Goal:

Establish/finish the smallest safe canonical Department Portal week surface.

Required direction:
- route opens reliably
- current Yuplan shell
- existing tenant/site/department scope
- canonical published Builder menu
- existing department menu-choice truth
- registered needs read-only where already supported
- no portal-specific shadow menu truth
- no duplicate department-choice model
- no broad portal redesign
- no broad cleanup of older portal routes

The order explicitly told Copilot to:
- reread only the relevant seam
- verify auth/scope
- use canonical publication
- preserve existing choice storage
- avoid a new generic portal framework
- test real browser at 1440x900, 1024x768, 768x1024
- stop with no commit for review

The next chat must review that report before deciding Gate 2.

---

# 5. PORTAL ARCHITECTURE THAT MUST NOT CHANGE

Source lock:

`docs/ground_truth/PORTALS_ARCHITECTURE_LOCK.md`

Core rule:

**Portals are experience and communication layers, not production engines.**

Department Portal:
- scoped to a department
- shows published menu
- shows menu choices
- may show relevant registered dietary/deviation information
- residents/special-diet production statistics are read-only
- menu choice is a legitimate portal user action
- portal must not become a second production truth
- private Cook/Work Menu state must not leak into external portal truth

Shared Portal Foundation may later serve Kommun + Offshore, but do not prematurely force all business domains into one generic model.

---

# 6. BUILDER EDITORS — ACCEPTED AND CLOSED FOR 1.0

## Accepted Dish editor

Tabs:
- Översikt
- Komponenter
- Kalkyl
- Allergener / kostinfo

Accepted:
- canonical same-page shared editor
- compact component block language
- Overview horizontal rail
- horizontal rail native scrollbar hidden
- dynamic left/right rail fades
- summary-first Kalkyl
- inline expandable Component detail
- one accordion row open at a time
- shared calculation truth with Component
- Swedish allergen presentation names
- Dish allergen data is read-only aggregation from Components
- modal native vertical scrollbar hidden
- dynamic top/bottom vertical fades

## Accepted Component editor

Tabs:
- Översikt
- Recept & metod
- Kalkyl
- Allergener / kostinfo

Accepted:
- same Yuplan font stack as Dish
- `KOMPONENT` Swedish header
- visible label `Beskrivning`
- no permanent `Komponentdetaljer laddade.` success banner
- context-aware return:
  - direct Library -> Tillbaka till komponenter
  - from Dish -> Tillbaka till <dish>
- modernized recipe rows
- modernized costing rows
- recipe-derived fields visually read-only
- price fields editable
- current allergen editor visually aligned
- native vertical scrollbar hidden
- top/bottom fades
- no nested horizontal scrollbars at desktop/tablet acceptance sizes

## Local data note

A local DB value:

`builder_library.db -> kottbullar.long_description_text = "Live return test note"`

was traced as a local DB value, not a source literal.

User explicitly confirmed it was unwanted.

It was cleared locally only.

The DB was NOT committed.

Do not reintroduce this value.

---

# 7. SHARED CALCULATION TRUTH

Accepted checkpoint before final editor finish:

`1798dddff9e2a8146a0fa1945c836f281db6829b`

`refactor(builder): share calculation truth across editors`

Current truth:
- Component and Dish share one frontend calculation utility
- Dish does not implement a second formula
- backend persists calculation rows but does not regenerate row cost
- shared helper is current Builder quantity/cost frontend truth

Reference Component:

`Potatismos`

Verified values:
- potatis 80 g @ 11 kr/kg -> 0.88 kr
- mjölk 60 g @ 21 kr/kg -> 1.26 kr
- smör 30 g @ 95 kr/kg -> 2.85 kr
- total 4.99 kr

Supported current helper behavior includes existing combinations around:
- g / kg
- ml / dl / l
- kr/kg
- kr/l
- st / kr/st

Do not add ingredient density conversion during Kommun closure.

---

# 8. BUILDER 1.1+ — DEFERRED PRODUCT DIRECTION

Do not implement before Yuplan 1.0 pilot closure unless a real blocker appears.

## Builder role

The main Builder should become Yuplan's advanced authoring workspace.

Normal daily users should often enter canonical Dish/Component editors from Kommun/Offshore operational flows rather than live in the full Builder workspace.

The current Builder Home/dashboard is recognized as prototype/old workspace IA and should later receive a proper redesign.

## Recipe -> costing

Locked future direction:

**Recipe ingredients are the default source of costing quantities.**

Future behavior:
- recipe row automatically appears in costing
- recipe row may be excluded from costing without being deleted from recipe
- extra costing-only rows may exist
- `Synka från recept` should eventually become reconciliation/update behavior rather than required initial duplication

## Canonical Ingredient Library

Future canonical Ingredient should enable:
- reusable identity instead of free-text-only matching
- aliases
- reusable standard price
- price unit
- price history
- later supplier/product mapping

Example:
- Potatis standard price = 11 kr/kg
- next recipe using Potatis should not require typing 11 kr/kg again
- recipe-local override remains possible

## Unit/conversion profiles

Future hierarchy:

Recipe-specific override
-> organization custom conversion
-> Yuplan standard
-> no safe conversion

Exact dimension conversions remain system rules.

Ingredient-specific volume-to-weight conversions may be custom.

Example:
- Linfrö Yuplan standard: 1 dl = 70 g
- local kitchen override: 1 dl = 67 g
- a baker may save own measured truth

Potential settings area:
`Inställningar -> Ingredienser & omvandlingar`

## Recipe import

Future flow:
- one Importera entry point
- paste recipe text
- upload document
- detect Menu / Dish / Recipe
- recipe import creates Recipe Draft
- Component match/attach/create review
- original source preserved
- normalization/additional conversion later
- bulk recipe library import later

Future-lab document exists on a separate documentation branch:

`docs/future-lab-builder-recipe-import-2026-10-01`

File:

`docs/future-lab/BUILDER_RECIPE_IMPORT_AND_UNIT_NORMALIZATION.md`

Do not mix this into current Kommun closure.

---

# 9. KOMMUN CORE — ACCEPTED PRODUCT CHAIN

Accepted chain:

Registered needs
-> varied/current quantities
-> published menu + department choices
-> Product2 Page1
-> Page2 human review
-> Planera 2.0
-> Page3 Produktionsunderlag
-> Mark complete
-> Kitchen Weekview
-> persistence
-> Admin Weekview
-> Reports

Principles:
- published menu is canonical menu truth
- menu choice is explicit truth
- missing menu choice does not silently fall back
- current quantities are business truth
- requirement groups are disjoint recipient cohorts
- multi-requirement recipients are counted once
- primary/modifier specialkost semantics are explicit
- Planera 2.0 Core remains generic
- Kommun-specific semantics stay in adapter/application/presentation layers

Known Product2 proof:
- Vardagsgryta: total 79, normal 79, special 0
- Ugnsbakad fisk: total 62, normal 54, special 8

A realistic isolated E2E Kommun fixture exists with 18 departments and canonical menu/requirement data.

---

# 10. PLANERA 2.0 — DO NOT REBUILD

Planera 2.0 is already far along.

Mental model:
- normalkost = baseline / single source of normal truth
- specialkost = deviations
- determine who cannot eat normalkost
- engine produces normal count + deviations + production underlag

Architecture:
- Builder owns Components -> Compositions/Dishes -> Menus -> Published Menu
- Planera 2.0 consumes published menu through adapters
- Core remains generic
- business-specific modules adapt into Core

Do not reopen Planera 2.0 architecture while closing Kommun 1.1.

---

# 11. PATH AFTER THE CURRENT PORTAL REPORT

Do not skip ahead before reviewing the report.

Expected remaining order:

## A. Department Portal
- review Gate 1 report
- approve/adjust smallest next gate only
- canonical route
- explicit menu choices
- read-only registered needs
- auth/scope
- tablet

## B. Meal-path verification
Lunch is proven.

Verify:
- dinner/evening path
- dessert mapping where applicable
- current Product2 mapping
- no Kommun assumptions leaking into Core

Verification-first.

## C. iPad/tablet operational pass
Priority:
- 1024x768
- 768x1024

Test only pilot-relevant operational paths.

## D. Final fresh Kommun pilot smoke
Must include:
- cold restart
- login repeatability
- canonical tenant/site
- published menu
- department choices
- registered needs
- Page1 -> Page2 -> Planera 2.0 -> Page3
- mark complete
- Weekview persistence
- Department Portal
- reports already in locked scope
- browser/console/request cleanliness

## E. Declare Kommun 1.1 PILOT READY

Only after fresh smoke.

## F. Controlled Planera transition

Run Planera 1 and Planera 2 side-by-side during real operational weeks.

Planera 1 remains temporary fallback.

Do not remove until real-week parity is proven.

## G. Return to Offshore 1.0

After Kommun closure, continue the already locked Offshore MVP scope.

Do not mix Offshore completion into current Kommun gates.

---

# 12. THINGS THE NEXT CHAT MUST NOT DO

Do NOT:
- send multiple Copilot orders before reports return
- reopen Builder modal micro-polish
- redesign Builder Workspace now
- implement Ingredient Library now
- implement Recipe Import now
- implement conversion profiles now
- build Home
- build Hotel/Banquet
- broad-refactor Portal architecture
- create a new generic portal data model
- duplicate menu truth
- duplicate department-choice truth
- put Kommun semantics into Planera 2.0 Core
- clean legacy code “while here”
- build a broad E2E suite before pilot closure
- guess local credentials
- assume GitHub remote dev HEAD equals local current HEAD

---

# 13. PROJECT MANAGEMENT STYLE

The user wants decisive project leadership, not lots of coding from ChatGPT.

Preferred behavior:
- give Copilot exact implementation orders
- explicitly state allowed/not allowed scope
- preflight branch/head/status
- use small gates
- require focused tests
- require live browser proof where UX matters
- no commit until user/reviewer accepts
- then checkpoint quickly
- move forward

User prefers speed toward MVP over perfect architecture/polish.

Browser evidence is final UX truth.

A visually wrong screen is not accepted because a test says green.

---

# 14. FIRST RESPONSE IN THE NEW CHAT

When the user starts the new chat, the correct response pattern is:

1. confirm that the handoff has been read
2. state the accepted local checkpoint:
   `bda732af9893b591856b658f034fc6a5f2580589`
3. state that Shared Dish + Component editors are CLOSED / Yuplan 1.0-ready
4. state that the active gate is Department Portal Gate 1
5. **ask for / review the Copilot report already in progress**
6. do not send a new Copilot order until that report is reviewed

If the user immediately pastes the report, skip all ceremony and review it.

---

# 15. SOURCE DOCUMENTS TO READ IF NEEDED

Primary:
- `docs/ground_truth/YUPLAN_1_0_FINISHLINE.md`
- `docs/ground_truth/PORTALS_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/BUILDER_MENU_LOCK.md`
- `docs/ground_truth/PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `docs/ground_truth/KOMMUN_1_0_MVP_LOCK.md`

This handoff overrides stale status paragraphs in older handoffs but does not override locked architecture unless explicitly stated.

---

# 16. ONE-LINE PROJECT STATE

**Builder shared editors are finished for 1.0; Kommun production core is established; Department Portal is the active gate; then meal-path verification -> tablet -> fresh pilot smoke -> Kommun 1.1 PILOT READY -> controlled Planera transition -> Offshore 1.0.**
