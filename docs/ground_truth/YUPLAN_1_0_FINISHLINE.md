Status: LOCKED
Last reviewed: 2026-09-23

# Yuplan 1.0 Finishline

## Current Phase

The shared Builder/Menu/Offshore seam remains accepted and frozen.

Active phase: Yuplan Kommun 1.0 — Planera 2.0 integration, production output and operational packing.

Portal / Department choice work has progressed far enough to support the current Planera 2.0 Product2 flow. Remaining portal polish is still required before pilot acceptance, but the main development path is now the end-to-end production chain.

Broad Builder/Menu MVP work remains closed. Only pilot-blocking regressions may reopen that seam before Kommun 1.0 Ready for Pilot.

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
- A realistic isolated Product2 E2E tenant exists with normal authenticated kitchen login, 18 departments, published menu, menu choices and canonical requirement cohorts.
- The E2E environment proves normal login -> Product2 Page1 -> Page2 through the real application path.
- Existing Kommun Serveringstillägg is a valid current operational input and must be preserved during migration.
- Existing production-list snapshots already demonstrate that Serveringstillägg can be shown with totals and department breakdown.

## Current Active Gate

Meal-level orchestration for Kommun Product2.

Purpose:
- assemble all current published meal options
- keep unassigned destinations explicit
- require current review only for options with demand
- run reviewed demanded options through Planera 2.0 acceptance and engine
- expose structured per-option production results for Page3
- preserve multiple readiness blockers without inventing fallback production

This gate must complete before Page3 is treated as production-ready.

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
8. Meal-level orchestration — ACTIVE.
9. Page3 Produktionsunderlag consuming real Planera 2.0 results.
10. Full authenticated Kommun E2E: Published Menu -> Department choice -> Page1 -> Page2 -> Planera 2.0 -> Page3.
11. Planera 1 / Planera 2.0 parallel run and parity review.
12. Daily destination-aware packing projection.
13. Preserve existing fixed Serveringstillägg in production / packing output.
14. Validate standing-needs modernization path without hardcoding only current Mos/Sallad/Ovrigt families.
15. Finish Department Portal / iPad / auth / print / operational polish.
16. Kommun 1.0 Ready for Pilot.
17. Return main development focus to Offshore 1.0.

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

Existing Serveringstillägg must be carried into this output during transition.

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
-> Meal orchestration
-> Page3 production output
-> parity
-> packing
-> operational polish
-> Kommun 1.0 Ready for Pilot

Do not list unrelated Offshore expansion work as a blocker for Kommun launch.

## Related Ground Truth

- `KOMMUN_1_0_MVP_LOCK.md`
- `PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `PORTALS_ARCHITECTURE_LOCK.md`

Detailed operational reference:
- `../planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md`
