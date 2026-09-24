Status: LOCKED
Last reviewed: 2026-09-24

# Yuplan 1.0 Finishline

## Current Phase

The shared Builder/Menu/Offshore seam remains accepted and frozen.

Active phase: **Yuplan Kommun 1.0 — Product2 Page3 Produktionsunderlag, explicit Specialkost hierarchy, production parity and operational packing.**

Portal / Department choice work has progressed far enough to support the current Planera 2.0 Product2 flow. Remaining portal polish is still required before pilot acceptance, but the main development path is now the end-to-end production chain and its operational UI.

Broad Builder/Menu MVP work remains closed. Only pilot-blocking regressions may reopen that seam before Kommun 1.0 Ready for Pilot.

## Current Checkpoint

Active development branch:

`feat/planera-app-shell-2026-03-03`

Last code checkpoint before this documentation update:

`77d73e637f055378b5e82a9385170b9e84346373`

`checkpoint(planera): align page3 information architecture`

That checkpoint is intentionally **not** a visual acceptance point. It preserves the current Page3 alignment work while known visual and interaction debt remains.

## Already Established

- Builder is the canonical knowledge source.
- Components -> Dishes/Compositions -> Menus -> Published Menu.
- Published menu projection is the source for Product2 meal options.
- Department menu choices are explicit; missing choice does not silently fall back.
- Product2 Page1 day overview exists.
- Product2 Page2 human review exists.
- Option review persistence and review staleness are established.
- Requirement groups use disjoint recipient-cohort semantics.
- Multi-requirement recipients are counted once in one combined cohort.
- Current quantities remain business truth; persisted review stores the human yes/no decision.
- Review-aware Kommun -> Planera 2.0 adapter is accepted and checkpointed.
- The adapter can produce a PlanningSlice from the current published option, assignment, review and current requirement quantities.
- Planera 2.0 Core can calculate baseline, deviation and normal production with destination/unit breakdown.
- Meal-level Kommun Product2 orchestration is accepted and complete.
- Orchestration keeps unassigned destinations explicit, requires current review only for demanded options, skips zero-demand options safely and preserves blockers without inventing production.
- Page3 has an authoritative VM/projection path that consumes Planera 2.0 production truth.
- A realistic isolated Product2 E2E tenant exists with normal authenticated kitchen user, 18 departments, published menu, menu choices and canonical requirement cohorts.
- Known READY proof remains:
  - Vardagsgryta: total 79, normal 79, special 0.
  - Ugnsbakad fisk: total 62, normal 54, special 8.
- Existing Kommun Serveringstillägg is valid current operational input and must be preserved during migration.
- Existing production-list snapshots already demonstrate that Serveringstillägg can be shown with totals and department breakdown.
- Product2 Page3 local tab switching exists as an implementation foundation; final visual acceptance is still pending.

## Current Active Gate

### Page3 Produktionsunderlag — final information architecture and visual recovery

The target Page3 mental model is locked:

**One production context -> three equal work tabs -> one active work area.**

Main tabs:
- Översikt
- Normalkost
- Specialkost

Only one main work area may be visually active at a time.

The target Page3 direction is:

### Shared header / context
- global Yuplan topbar remains unchanged
- compact page title: Produktionsunderlag
- operational date context, not a giant decorative hero
- kitchen/site + meal context
- quiet action back to review
- review-oriented status wording: **Underlag granskat**, not a generic production-completion "Klar"

### Översikt
One compact production table. No duplicate summary cards and no large per-dish cards.

Columns:
- Menyval
- Totalt
- Normalkost
- Specialkost

Values must come from authoritative Page3 / PlanResult truth.

### Normalkost
Compact destination x published-menu-choice matrix.

Rules:
- department/destination first column
- dish/menu choices as columns
- dish title + total quantity in header
- zero shown as a quiet dash
- totals row at bottom
- horizontal scroll for many dishes rather than squeezing columns unreadably
- no accidental semantic row highlighting

### Specialkost
Final target presentation is **primary requirement -> recipient/destination rows -> optional modifiers**.

Example target:

`Timbal 13`

`Avdelning 11 [Ugnsbakad fisk] [Glutenfri] 1`

Where:
- the primary requirement owns the production group
- menu choice is neutral context only
- modifiers are visually distinct, planned as subtle purple pills
- a recipient/cohort is counted once under its primary production group
- grouping by `Avdelning | Menyval` is presentation only and must not change totals

Current persistence does **not yet** contain explicit primary/modifier semantics, so Page3 must not infer them from names, sort order or array order.

## Locked Specialkost Primary / Modifier Direction

The current requirement-group persistence stores an unordered exact member set. It cannot distinguish:

- primary Timbal + modifier Glutenfri

from:

- primary Glutenfri + modifier Timbal

The locked 1.0 direction is:

- add explicit primary semantics to the requirement group
- smallest preferred durable model: nullable `primary_requirement_id` on `department_requirement_groups`
- the full existing requirement-member set remains intact
- service validation requires the primary to be one of the group members
- all remaining members become modifiers
- Planera 2.0 Core remains generic and continues to consume the full exact combination
- primary/modifier is registration/application/presentation semantics unless a future production rule truly requires more

Migration rule:
- existing single-requirement groups are unambiguous and may use that sole requirement as primary
- existing multi-requirement groups are ambiguous and must not be guessed from name/order
- unresolved legacy combinations must be surfaced explicitly until resolved

Registration UX target:
- create/select the primary requirement first
- inside that primary requirement add 0..N additional requirements/modifiers
- user-entered hierarchy is authoritative

## Known Page3 Visual Debt at Current Checkpoint

The checkpoint `77d73e6...` still requires visual recovery before acceptance.

Observed current runtime issues include:
- old large date/hero treatment is still visible
- old `Klar` wording can still appear in runtime
- old `Tillbaka till granskning` presentation can still appear
- `Produktion / Per avdelning` subnavigation can leak into unrelated main views
- Översikt can render as raw/unstructured text instead of the intended compact table
- Specialkost still shows current exact-combination semantics because primary/modifier persistence is not implemented yet
- dark mode contains overly dark/flat sections and needs visual balancing
- final Light/Dark polish and tab isolation still require manual acceptance

Do not treat green unit/UI tests alone as visual acceptance.

## Product2 E2E Runtime Rule

The normal local debug/reloader path is currently **not trusted as the canonical visual-review runtime**.

A single-process E2E server has been proven to work with:
- `product2_e2e.db`
- `product2_e2e_builder.db`
- one process on port 5000
- `debug=False`
- `use_reloader=False`
- real live POST `/auth/login` returning success for the E2E kitchen user

Until runtime hardening is completed, visual review should use that deterministic single-process pattern.

A later small dev-runtime hardening gate should provide one deterministic Product2 E2E start command/script so review work cannot accidentally attach to `dev.db`, a stale reloader child, or a different process.

## Next Major Milestone

Yuplan Kommun 1.0 — Ready for Pilot.

Order:

1. Builder/Menu/Offshore seam freeze — COMPLETE.
2. Ground Truth / Planera 2.0 Architecture Lock — COMPLETE.
3. Portal Foundation / Department menu-choice canonical path — SUFFICIENT FOR ACTIVE PLANERA INTEGRATION; final polish remains.
4. Product2 Page1 / Page2 flow — COMPLETE FOUNDATION.
5. Option review persistence / staleness — COMPLETE.
6. Review-aware Kommun -> Planera 2.0 adapter — COMPLETE.
7. Realistic 18-department Product2 E2E environment — COMPLETE.
8. Meal-level orchestration — COMPLETE.
9. Page3 authoritative production projection — COMPLETE FOUNDATION.
10. Page3 final information architecture / Light-Dark visual acceptance — ACTIVE.
11. Explicit Specialkost primary/modifier persistence + registration/application projection.
12. Final Specialkost Page3 projection using primary groups, neutral menu-choice context and modifier pills.
13. Full authenticated Kommun E2E: Published Menu -> Department choice -> Page1 -> Page2 -> Planera 2.0 -> Page3.
14. Planera 1 / Planera 2.0 parallel run and parity review.
15. Daily destination-aware packing projection.
16. Preserve existing fixed Serveringstillägg in a separate Servering / Packning operational surface; do not mix them into the default normal/specialkost production worklist.
17. Validate Serveringsanpassning modernization without hardcoding only current Mos/Sallad/Ovrigt families.
18. Finish Department Portal / iPad / auth / print / operational polish.
19. Kommun 1.0 Ready for Pilot.
20. Return main development focus to Offshore 1.0.

## Kommun 1.0 Packing Finishline

A production total alone is not enough for Kommun operations.

Before Kommun 1.0 is considered operationally pilot-ready, Yuplan must be able to derive a daily pack-oriented view that answers:

- what should be packed
- how much
- for which date and meal
- to which department / destination
- which production item is standard or adapted
- which existing standing additions / handling requirements also apply

The packing layer must consume shared production / operational truth. It must not become a second calculation engine.

Specialkost production and Serveringsanpassning remain separate operational tracks. Existing Serveringstillägg must be carried into a separate Servering / Packning surface during transition and must not clutter the default normal/specialkost production worklist.

A later optional total pack list may explicitly combine both tracks for one department, one delivery location or all destinations, for example: Normalkost 8, Timbal 1, Sallad 6 — aldrig tomat, Potatismos istället för kokt potatis 1. This combined view is a downstream projection only; it does not merge the underlying domains.

The architecture must also remain open to future menu-aware substitutions such as:
- boiled potato -> mashed potato
- pasta -> mashed potato
- spaghetti -> macaroni
- component exclusions such as never tomato
- handling instructions such as sauce separately

A full arbitrary rule editor is not required to block the first pilot if the architecture and migration path are already safe.

## Parallel Run / Cutover

Planera 1 remains the current comparison baseline during transition.

Before Planera 2.0 becomes Kommun production truth:
- compare source departments
- compare baseline quantities
- compare menu choices
- compare specialkost / requirement quantities
- compare normal / standard production
- compare adaptations
- compare destination breakdown
- compare existing Serveringstillägg totals where applicable

A difference must be classified as:
- regression
- legacy limitation
- intentional improved behavior

Do not force Planera 2.0 to reproduce a known legacy limitation merely to achieve numerical equality.

## Freeze Point

Builder/Menu/Offshore broad MVP work remains frozen.

The main launch path is now:

Kommun Product2 flow
-> Page3 visual/product acceptance
-> explicit Specialkost primary/modifier semantics
-> final Specialkost production projection
-> full production E2E
-> production parity
-> separate Servering / Packning projection
-> optional combined total-pack projection
-> operational polish
-> Kommun 1.0 Ready for Pilot

Do not list unrelated Offshore expansion work as a blocker for Kommun launch.

## Related Ground Truth

- `KOMMUN_1_0_MVP_LOCK.md`
- `PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `PORTALS_ARCHITECTURE_LOCK.md`

Detailed operational reference:
- `../planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md`
