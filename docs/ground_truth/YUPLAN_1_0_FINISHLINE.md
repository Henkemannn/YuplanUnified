Status: LOCKED
Last reviewed: 2026-10-07

# Yuplan 1.0 Finishline

## Current Phase

Active phase:

**Kommun 1.1 — close Menyimport canonical editing/open behavior, then global responsive/tablet pass, fresh pilot smoke, and pilot readiness.**

The broad Builder/Planera architecture is not being reopened.

The current blocker is a narrow integration seam:

- canonical menu import works
- canonical week draft works
- canonical `Byt rätt` bind works
- shared canonical search runtime exists
- the remaining unresolved integration is opening an existing resolved Dish from the week/menu surface in the already-finished shared Dish editor

Do not broaden this into a new Builder, new modal system, new search implementation, Offshore migration, or responsive redesign.

## Current committed checkpoint

Active development branch:

`feat/planera-app-shell-2026-03-03`

Last committed stable checkpoint:

`a0c84db762567c03b68fac8a3b66457c5358ad23`

`fix(kommun): harden weekview pilot feature flag`

GitHub remote development branch currently points to the same commit.

Important:

**All current Menyimport work after `a0c84db` is uncommitted local work.**

Do not infer the current local implementation from GitHub remote source alone.

Before implementation work, confirm local truth with:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

## Safety snapshot

Verified snapshot of the current local worktree:

`C:\Users\Henrik Jonsson\Yuplan Unified\backups\YuplanUnified_PRE_RECOVERY_2026-10-07_201644.tar.gz`

The snapshot preserves:
- modified tracked source files
- all six untracked source files
- Git metadata / status / diff
- current local Menyimport work

Runtime DBs and heavy generated folders are excluded.

A later failed restore pass changed three files, and those three were subsequently restored byte-for-byte from the snapshot with matching SHA256 hashes.

Therefore the current local worktree is back at the verified snapshot state.

## Closed Kommun desktop gates

The following are functionally closed for the current desktop pass:
- Department/Kostbehov flow
- Kostbehov lifecycle
- Serveringsanpassningar
- contextual Kostbehov consistency
- Department identity / residence presentation
- all-departments Weekview
- Weekview desktop density/layout
- Weekview completion interaction
- Weekview pilot feature-flag hardening

Important accepted commits include:

- `154c422ffecf2376318060d5681a763a75011e62`
- `5989e9e60ae2c19e099a2379d7ea86dcae23b737`
- `37178ac5b839f2bad3358584a24e6fa5c793349d`
- `99fbc4d599e7893beb6f3a63592cf0d8a5f94bee`
- `3d84ca2a99e8da7914e69125d3d37169823db833`
- `67f0265e1f05a89d653068b6c28308bc57aa1a08`
- `efccfc75badc2439e7ccdee8dff7e7ee6f2a0c85`
- `d92dcc9873aab6ee13891b47ce8dbbceab9cd239`
- `21559c7ff9eb958bcb53717abd6e682c7a90f3a7`
- `a0c84db762567c03b68fac8a3b66457c5358ad23`

## Weekview product lock

Weekview is an overview/facit/fallback surface.

It is **not** the primary production-calculation surface.

Planera remains the primary production workflow.

Weekview must:
- show resident totals
- show Kostbehov
- show variations
- show meal context
- show kitchen completion state

Weekview must not derive/show Normalkost.

Kitchen may toggle completion.

Admin sees completion read-only.

Green circle = completed.

No circle = no completion mark; it does not mean failed or remaining.

## Kostbehov truth

User-facing term: **Kostbehov**.

Resident count = total people.

Active requirement groups are additive.

Composite requirement groups count once.

`special_diet_total(context)` is the sum of effective quantities of active requirement groups.

`Normalkost = resident_count - special_diet_total`.

Normalkost is derived, never manually stored.

100% Kostbehov is valid.

>100% is invalid.

Effective quantity precedence:

exact service date + meal
-> weekday + meal
-> default

No silent clamping.

## Current active gate — Menyimport canonical editing

The Menyimport gate is currently uncommitted.

### Proven

Real import UI with `sample_menu.csv`:
- detected 2025 W49 from source
- imported successfully
- produced canonical Builder-linked draft
- week page renders canonical rows

Successful live bind:
- imported unresolved `Köttbullar`
- bound to `Köttbullar med potatismos`
- canonical composition id: `cmp_endp4l`

Correct bind ownership:
- picker returns `composition_id`
- week/menu caller preserves `day` and `meal_slot`

### Canonical ownership

Builder/domain owns:
- Components
- Dishes/Compositions
- library
- composition identity
- shared Dish editor
- shared Component editor
- composition-search semantics

Week/menu UI owns:
- week/day context
- meal slot
- placement/action context

There must not be a second Builder implementation inside Menyimport.

### Locked action matrix

Resolved Dish:

- direct Dish-name click -> existing finished shared Dish editor
- `⋯ -> Öppna rätt` -> same existing finished shared Dish editor
- `⋯ -> Byt rätt` -> Rättbibliotek picker
- `⋯ -> Ta bort från menyn` -> remove menu placement only

Unresolved imported text:
- ordinary menu text
- no technical status such as `Ej kopplad`
- may prefill Rättbibliotek query
- resolution path is `Byt rätt`

### Shared search runtime

`static/js/builder_composition_search.js`

is the canonical shared composition-search runtime.

Both Builder and Rättbibliotek must use it.

Current supported semantics are name/id.

Tag/hashtag search is deferred until implemented once in this shared runtime.

No picker-specific matcher.

## Existing-Dish editor regression

The historical working integration exists in Git history.

Key references:

`dd7ffac54593ac114975d78a49b2f4c586caf4f0`
`feat(kommun): edit menu dishes in shared builder overlay`

`fd9ca3aa9668d91f9130ba19c44ce4deeeca67ca`
`style(kommun): flatten shared dish editor overlay`

`cbc2cef3c02c511570c529dc7c348bf5d6fedf15`
`fix(builder): preserve component return context`

Later accepted editor improvements:

`2e0793aa752b3cc8dcb844118e38529769f08af5`

`1798dddff9e2a8146a0fa1945c836f281db6829b`

`bda732af9893b591856b658f034fc6a5f2580589`

Historical integration model:

Menyimport parent
-> frosted overlay
-> isolated editor host iframe
-> `/builder-editor-host?composition_id=<id>`
-> shared Dish editor

A later attempt mounted Builder modal/runtime directly in the week parent and visually broke the App Shell.

That architecture is rejected.

## Next gate — read-only forensic comparison

Do not implement first.

Compare:

A. historical working integration:
- `dd7ffac`
- `fd9ca3aa`
- `cbc2cef3`

B. later accepted shared editor:
- `2e0793aa`
- `1798ddd`
- `bda732`

C. current verified snapshot worktree

Trace independently:
1. direct resolved Dish click
2. `Öppna rätt`
3. `Byt rätt`

Find the first exact divergence.

Then propose the smallest patch **without applying it**.

Strong target:
- no more than four production files
- Offshore out of scope
- no new modal
- no new Builder page
- no duplicate search runtime
- no broad cleanup

Only after review may implementation start.

## Copilot execution rule

During MVP closure, Copilot does not own surrounding architecture.

For every implementation order:

> **You are implementing one approved seam, not owning the surrounding architecture. Any necessary change outside explicitly allowed files is a STOP condition.**

Also:
- audit orders are read-only
- one order -> one report -> review -> next order
- no “while here” refactors
- do not follow collateral effects into another module
- do not change production behavior simply because an existing test expects it
- real-browser evidence outranks green DOM/unit tests for UX acceptance

## Responsive status

Responsive work is deliberately parked until desktop functional closure.

Observed:
- iPhone App Shell compresses badly
- Weekview table compresses badly

Planned order:
1. global responsive shell / breakpoints / tokens
2. iPad/tablet operational acceptance
3. module content
4. iPhone/mobile
5. consolidated polish

Do not mix responsive work into the current Menyimport/Dish-open gate.

## Remaining path to Kommun pilot readiness

1. Read-only forensic comparison of existing-Dish open integration.
2. One minimal reviewed Dish-open patch.
3. Live user acceptance:
   - direct click opens shared Dish editor
   - Öppna rätt opens same editor
   - Byt rätt opens Rättbibliotek
4. Rättbibliotek visual acceptance.
5. Clean focused tests + understood diff.
6. Commit current Menyimport work in coherent checkpoints.
7. Global responsive/tablet pass.
8. Fresh Kommun pilot smoke.
9. Declare Kommun 1.1 PILOT READY.
10. Controlled Planera transition / real-week parity.
11. Return to Offshore 1.0 closure.
12. Yuplan 1.0 release gate.

## Scope excluded from the current gate

Do not reopen unless a proven pilot blocker requires it:
- broad Builder Workspace redesign
- Ingredient Library expansion
- Recipe Import
- conversion profiles
- Home
- Hotel/Bankett
- broad Offshore work
- broad dead-code cleanup
- generic portal/platform refactors

## Related ground truth

- `KOMMUN_1_0_MVP_LOCK.md`
- `PLANERA_2_0_ARCHITECTURE_LOCK.md`
- `PORTALS_ARCHITECTURE_LOCK.md`
- `BUILDER_MENU_LOCK.md`
- `KOMMUN_MENUIMPORT_EDITING_LOCK.md`

## One-line finishline state

**Kommun desktop core and Weekview are closed; Menyimport canonical import/selection/bind largely works; existing-Dish open integration is the active blocker; the current local work is safely snapshotted; next action is a read-only historical/current comparison followed by one minimal reviewed patch, then responsive/tablet and pilot smoke.**
