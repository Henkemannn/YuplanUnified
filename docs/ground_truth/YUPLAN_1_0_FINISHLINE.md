Status: LOCKED
Last reviewed: 2026-09-28

# Yuplan 1.0 Finishline


## Current Phase

The shared Builder/Menu/Offshore seam remains accepted and frozen.

Release naming is now explicit:
- **Kommun 1.0** = existing legacy/pilot comparison baseline.
- **Kommun 1.1** = the current Product2 + Planera 2.0 track being finished for the next pilot.
- **Yuplan 1.0** = the wider platform MVP finishline that combines a pilot-ready Kommun track with Offshore 1.0.

Active phase: **Kommun 1.1 — close the Product2 Page3 -> Weekview completion chain, then reporting/parity and pilot hardening.**

The Page3 information architecture and Specialkost hierarchy are no longer the main development blocker. Primary/modifier persistence, recurring cohort quantities, cohort Weekview projection and the Kitchen completion write path are implemented. Final micro-polish is deliberately deferred until the remaining functional bridges and E2E/parity checks are complete.

Broad Builder/Menu and Offshore MVP expansion remains closed. Only pilot-blocking regressions or shared-platform issues may reopen those seams before Kommun is pilot-ready.


## Current Checkpoint

Active development branch:

`feat/planera-app-shell-2026-03-03`

Latest accepted local code checkpoint before the current uncommitted UI/E2E gate:

`2364ba475a7ed8d16087d7f60f9fadf25756c945`

`feat(planera): add product2 cohort completion api`

Important earlier checkpoints in the current completion chain include:
- `3daed7e742bc7599148994de63756b5e4f6a3e54` — Kitchen Weekview cohort completion.
- `fef21ea3988b67881d8748efdd362dcbcb720362` — exact Product2 Page3 cohort completion targets.
- `5f590346be34204df0cc6b928a97265fc0385ecd` — atomic multi-department cohort completion coordinator.
- `2364ba475a7ed8d16087d7f60f9fadf25756c945` — Product2 completion API with per-department ETag concurrency.

Current local uncommitted gate:
- Page3 visible completion action and client flow.
- removal of an incorrect legacy `ff.planera.enabled` guard from the Product2 completion POST.
- deterministic completion E2E scenario cleanup so the final manual proof starts from known review and Alt 2 state.

Do not checkpoint that uncommitted gate until the clean manual Page3 -> Kitchen Weekview -> reload -> Admin Weekview proof passes.


## Already Established

- Builder remains the canonical knowledge source: Components -> Dishes/Compositions -> Menus -> Published Menu.
- Published-menu projection is the source for Product2 meal options.
- Department menu choices are explicit; missing choice does not silently fall back.
- Product2 Page1 day overview exists.
- Product2 Page2 human review exists.
- Option-review persistence and review staleness are established.
- Requirement groups use disjoint recipient-cohort semantics so one recipient with multiple requirements is counted once.
- Explicit Specialkost primary semantics are persisted through `primary_requirement_id`; the full exact requirement-member set remains intact and all non-primary members are modifiers.
- Recurring/variable cohort quantity is persisted per registered need with precedence exact service date + meal -> weekday + meal -> default, including valid zero quantities.
- Review-aware Kommun -> Planera 2.0 adaptation is established.
- Planera 2.0 Core calculates baseline, normal production and adaptation quantities while remaining generic and Kommun-agnostic.
- Meal-level Product2 orchestration is established and preserves blockers/unassigned destinations without inventing production.
- Page3 has an authoritative Planera 2.0-backed production VM.
- Page3 Specialkost presentation uses the explicit primary/modifier semantics instead of guessing from names or order.
- Admin and Kitchen Weekview reuse the existing shared week-grid surface; no third Weekview has been introduced.
- Cohort Weekview projection is established and keeps one registered need as one row, including separate rows for same-primary cohorts.
- Cohort completion persistence is independent from legacy `weekview_registrations`.
- Kitchen Weekview can mark cohort rows done while Admin Weekview remains read-only.
- Weekview base-version compare-and-bump exists and the cohort write path is atomic.
- Multi-department completion is atomic: all department CAS checks succeed before completion writes, with one commit and full rollback on stale/error.
- Product2 Page3 exposes exact server-side completion targets from `planning_slice.context["requirement_group_refs"]`; it does not use labels, combinations or diet-type IDs as mutation identity.
- Product2 completion API derives targets server-side, validates the exact effective-ETag set for all affected departments, hands base versions to the atomic coordinator and returns fresh per-department ETags.
- Manual live proof has already shown the Page3 completion action can reach success state and mark the corresponding cohort rows in Kitchen Weekview.
- The completion write path touches cohort completions + Weekview versions only; Alt 2 is a separate `department_menu_choices` truth.
- A live yellow-cell investigation proved the observed Alt 2 state came from pre-existing E2E menu-choice data, not from completion writes.
- Existing Serveringstillägg remains valid operational input and must be preserved in a separate Servering / Packning track.


## Current Active Gate

### Close the Page3 -> Weekview completion E2E

This is a finish-the-existing-gate task, not a new test-infrastructure project.

Required clean proof:
1. prepare a minimal deterministic completion scenario on top of the existing Product2 E2E seed;
2. Page2 truth yields exactly the intended four `ADAPTATION_REQUIRED` completion targets;
3. the target departments start with no completion mark and no confusing Alt 2 background for the target meal;
4. click Page3 `Markera som gjorda i veckolistan`;
5. Page3 enters `Markerat i veckolistan ✓` success state;
6. the exact cohort rows are marked in Kitchen Weekview;
7. reload preserves the marks;
8. Admin Weekview shows the same persisted truth read-only.

Scope guard:
- the deterministic scenario preparation must remain a very small fixture-only change;
- no generic E2E framework, seed-system refactor or product-code redesign is allowed for this gate;
- if the fixture work expands materially, stop and return to the product todo list.

### Current known E2E data caveat

The base Product2 E2E seed is intentionally generic:
- Page2 starts UNREVIEWED;
- Tuesday menu choices include seeded Alt 2 state for some departments.

Therefore a reused E2E database is not, by itself, a canonical completion scenario. A narrow scenario overlay/reset is needed for a clean manual before/after proof. This is test-fixture hygiene, not a completion-domain change.

### Completion semantics lock

`quantity` = planned production need.

`completion/done` = produced/handled operational outcome and future reporting input.

`Alt 2` = independent department menu-choice state.

These truths must remain independent:
- completion only -> green completion indicator, normal background;
- Alt 2 only -> yellow meal background, not completed;
- both legitimately true -> yellow background + green completion indicator.

Yuplan 1.1 does not perform external billing. Reporting/debiting integration remains downstream of the persisted completion + quantity truth.


## Product2 E2E Runtime Rule

Normal local development remains:

`python run.py`

which uses the ordinary local `dev.db` configuration.

Canonical Product2 E2E visual/manual review uses the separate disposable databases:
- `instance/product2_e2e.db`
- `instance/product2_e2e_builder.db`

Known-good runtime:
- one process on port 5000;
- `debug=False`;
- `use_reloader=False`;
- explicit E2E database configuration;
- real `/auth/login` session.

Verified E2E accounts:
- Kitchen/cook: `e2e.kitchen@yuplan.local`
- Admin: `e2e.admin@yuplan.local`

The E2E database must not be confused with `dev.db`. Reused E2E state may contain prior manual review, completion and menu-choice state, so destructive/manual acceptance scenarios must start from a deterministic reset/overlay.

A small developer-experience helper for deterministic E2E startup may be added later, but it is not allowed to become a launch-blocking side project.


## Next Major Milestone

**Kommun 1.1 — Ready for Pilot.**

Current order:

1. Builder/Menu/Offshore shared seam freeze — COMPLETE.
2. Planera 2.0 architecture lock — COMPLETE.
3. Product2 Page1 / Page2 foundation — COMPLETE.
4. Option review persistence / staleness — COMPLETE.
5. Explicit Specialkost primary/modifier persistence — COMPLETE.
6. Recurring/variable registered-need quantities — COMPLETE.
7. Review-aware Kommun -> Planera 2.0 adapter + meal orchestration — COMPLETE.
8. Page3 authoritative production projection and Specialkost hierarchy — COMPLETE FOUNDATION.
9. Shared Admin/Kitchen cohort Weekview projection — COMPLETE.
10. Kitchen cohort completion write with optimistic versioning — COMPLETE.
11. Page3 exact completion-target contract — COMPLETE.
12. Atomic multi-department completion coordinator — COMPLETE.
13. Product2 completion API + concurrency bridge — COMPLETE.
14. Page3 completion button/client + clean live E2E proof — ACTIVE, NEAR COMPLETE.
15. Reporting/statistics bridge consuming new cohort quantity + completion truth.
16. Full Kommun E2E: Admin registered need -> variable qty -> menu -> Planera -> production -> Kitchen Weekview -> completion -> report.
17. Kommun 1.0 vs Kommun 1.1 parity/cutover review; classify every difference as regression, legacy limitation or intentional semantics.
18. Consolidated UI/UX finish: compact variable-quantity editing, Specialkost/Registrerade behov presentation, empty/error/status states, iPad and Light/Dark consistency.
19. Separate Servering / Packning projection and preservation of existing Serveringstillägg.
20. Kommun 1.1 Ready for Pilot.
21. Fresh Offshore 1.0 census and finish after the Kommun gate is frozen.
22. Yuplan 1.0 release gate across included Kommun + Offshore surfaces.

## Kommun Product2 Packing Finishline

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

Page3 -> Weekview completion E2E
-> reporting/statistics bridge
-> full Kommun E2E
-> Kommun 1.0 / 1.1 parity and cutover
-> consolidated operational UI/iPad finish
-> separate Servering / Packning projection
-> Kommun 1.1 Ready for Pilot
-> Offshore 1.0 finish
-> Yuplan 1.0 release gate

Do not reopen broad Builder work, invent a third Weekview, rewrite working Kommun 1.0 surfaces unnecessarily, or turn E2E fixture cleanup into a separate multi-day project.

Out of Yuplan 1.0 MVP scope unless needed for a proven blocker:
- Yuplan Home;
- Hotel/Bankett/Event;
- advanced analytics;
- billing/Mathilda-style integrations;
- new recipe engine work;
- full dead-code cleanup.

## Related Ground Truth

- `KOMMUN_1_0_MVP_LOCK.md`
- `PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `PORTALS_ARCHITECTURE_LOCK.md`

Detailed operational reference:
- `../planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md`
