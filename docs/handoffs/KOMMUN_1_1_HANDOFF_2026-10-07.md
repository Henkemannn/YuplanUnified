# KOMMUN 1.1 HARD HANDOFF — 2026-10-07

Status: ACTIVE HANDOFF  
Purpose: start a new ChatGPT project-management thread without losing the exact current state  
Development branch: `feat/planera-app-shell-2026-03-03`  
Documentation branch only: `handoff/kommun-1-1-2026-10-07`

> **DO NOT DEVELOP ON THIS HANDOFF BRANCH.**
>
> This branch is documentation only.
> Product development continues locally on `feat/planera-app-shell-2026-03-03`.

---

# 1. FIRST INSTRUCTION TO THE NEXT CHAT

Act as project manager / technical lead for Yuplan Unified.

The user drives product decisions. GitHub Copilot in VS Code performs most implementation work.

Your job is to:
- hold architecture and product truth together
- choose the smallest safe next gate
- write exact Copilot orders
- review one Copilot report before any new order
- stop scope creep
- protect already accepted work
- treat the real browser as final UX truth

## Non-negotiable workflow

**ONE ORDER -> ONE COPILOT REPORT -> REVIEW -> NEXT ORDER**

Do not let Copilot broaden the task because it discovers adjacent code.

New authority boundary for implementation orders:

> **You are implementing one approved seam, not owning the surrounding architecture. Any necessary change outside explicitly allowed files is a STOP condition.**

Audit orders are read-only unless explicitly stated otherwise.

A failing test is evidence, not automatic authority to rewrite production behavior.

---

# 2. REPOSITORY / CHECKPOINT STATE

## Active development branch

`feat/planera-app-shell-2026-03-03`

## Last committed stable checkpoint

`a0c84db762567c03b68fac8a3b66457c5358ad23`

`fix(kommun): harden weekview pilot feature flag`

GitHub remote development branch currently points to the same SHA.

## IMPORTANT: CURRENT PRODUCT WORK AFTER a0c84db IS UNCOMMITTED

There is substantial current Menyimport work in the local working tree.

Do **not** use remote GitHub source after `a0c84db` as proof of the local current implementation.

Before any implementation in the new chat, Copilot must report:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

Expected HEAD:

`a0c84db762567c03b68fac8a3b66457c5358ad23`

The local working tree is intentionally dirty because the Menyimport gate has not been accepted/committed.

---

# 3. SAFETY SNAPSHOT — CRITICAL

Because the Menyimport recovery became tangled, a verified physical snapshot was created before any further rollback attempts:

`C:\Users\Henrik Jonsson\Yuplan Unified\backups\YuplanUnified_PRE_RECOVERY_2026-10-07_201644.tar.gz`

Verified:
- archive readable
- size: 32,470,323 bytes
- HEAD recorded as `a0c84db...`
- branch recorded as `feat/planera-app-shell-2026-03-03`
- modified tracked files preserved
- all 6 untracked source files preserved
- runtime DBs excluded
- Git status/diffstat unchanged by snapshot creation

A later failed restore attempt touched exactly:
- `static/js/builder_editor_host.js`
- `static/ui/admin_menu_import_week_actions.js`
- `static/offshore2/work_menu.js`

Those three files were then restored **byte-for-byte from the snapshot**, with SHA256 parity verified.

Therefore:

**Current local state = verified safety-snapshot state.**

Do not attempt to reconstruct or undo the failed restore pass again.

---

# 4. ACCEPTED KOMMUN WORK CLOSED IN THIS THREAD

The following desktop functional areas were closed and committed before the current Menyimport work.

Important commits include:

- `154c422ffecf2376318060d5681a763a75011e62` — close department Kostbehov flow
- `5989e9e60ae2c19e099a2379d7ea86dcae23b737` — close Kostbehov lifecycle
- `37178ac5b839f2bad3358584a24e6fa5c793349d` — close Serveringsanpassningar flow
- `99fbc4d599e7893beb6f3a63592cf0d8a5f94bee` — enforce contextual Kostbehov consistency
- `3d84ca2a99e8da7914e69125d3d37169823db833` — restore all-departments Weekview
- `67f0265e1f05a89d653068b6c28308bc57aa1a08` — preserve residence-only department edits
- `efccfc75badc2439e7ccdee8dff7e7ee6f2a0c85` — clarify Weekview department identity
- `d92dcc9873aab6ee13891b47ce8dbbceab9cd239` — align site-level Alt2 assertion
- `21559c7ff9eb958bcb53717abd6e682c7a90f3a7` — refresh Weekview desktop overview
- `a0c84db762567c03b68fac8a3b66457c5358ad23` — harden Weekview pilot feature flag

## Department / Kostbehov truth

- user-facing term is **Kostbehov**
- resident count = total people
- active requirement groups are additive
- composite requirement group counts once
- `special_diet_total(context) = SUM(effective quantity of each ACTIVE requirement group)`
- `Normalkost = resident_count - special_diet_total`
- Normalkost is derived, never manually stored
- 100% Kostbehov is valid
- >100% is invalid
- exact override > weekday override > default
- no silent clamping

Variation-modal rule:
- requirement-group quantity ±N changes resident count in the same cell ±N to preserve Normalkost
- direct resident-count edit does not auto-change requirement-group quantities

## Serveringsanpassningar

Functionally closed for current Kommun scope.

Specialkost/Kostbehov and Serveringsanpassningar remain separate domains.

---

# 5. WEEKVIEW — CLOSED FOR DESKTOP FUNCTIONAL REVIEW

Weekview is accepted at `a0c84db`.

Product role:

**Weekview = overview / facit / fallback.**
It is **not** the primary production-calculation surface.

Planera remains the primary production workflow.

Locked Weekview semantics:
- do not derive/show Normalkost in Weekview
- not all Kostbehov requires a daily adaptation
- show resident totals
- show Kostbehov
- show variations
- show lunch/evening
- show kitchen completion state
- Kitchen may manually toggle completion
- Admin sees completion read-only
- green circle = completed
- no circle = no done mark; not “failed” or “remaining”

Accepted desktop UI:
- seven days simultaneously visible
- day headings include dates
- compact week context
- stronger day separators than meal separators
- department identity: `Avdelning 1 / Solrosen`
- menu/book icon retained
- dense operational matrix

Feature-flag hardening at `a0c84db`:
- canonical pilot seed guarantees Weekview enabled for pilot tenant
- UI completion cells are noninteractive if backend flag is off
- global default remains unchanged

---

# 6. RESPONSIVE STATUS — DELIBERATELY PARKED

Responsive work is not the current blocker.

Observed on iPhone:
- App Shell compresses badly
- Weekview table compresses badly

Decision:
- finish desktop functional closure first
- then run one global responsive pass
- shared shell/breakpoints/tokens first
- then module content
- iPad/tablet is high priority
- iPhone follows

Do not let responsive cleanup reopen current Menyimport architecture.

---

# 7. CURRENT ACTIVE PHASE — MENYIMPORT / CANONICAL MENU EDITING

This entire gate is currently **UNCOMMITTED**.

## Import proof already achieved

Using the real UI and `sample_menu.csv`:
- Yuplan correctly detected year/week from source
- imported into 2025 W49
- import completed successfully
- W49 became a canonical Builder-linked draft
- no manual week picker was required

Current product decision:
- source document date/week detection remains normal import behavior
- future targeted import into a user-selected week/date is PARKED
- conflicts must never be silently guessed

## Canonical ownership

The canonical Builder/domain owns:
- Dishes/Compositions
- Components
- composition library
- menu content identity
- shared Dish editor
- shared Component editor
- canonical composition search semantics

The week/menu surface owns:
- week context
- day
- meal slot
- placement/action context

There must be **no “Builder on top of Builder.”**

Do not duplicate:
- Dish editor
- Component editor
- library/search semantics
- composition model
- menu truth

“Builder” is internal terminology. Avoid exposing it as the normal user-facing product name.

---

# 8. CURRENT W49 LIVE STATE

During the current gate, one intentional canonical bind was successfully proven:

Monday · Lunch alt 1:

old imported unresolved text:
`Köttbullar`

bound to canonical Dish:
`Köttbullar med potatismos`

canonical composition:
`cmp_endp4l`

The bind required the week caller to preserve:
- `day`
- `meal_slot`

while the picker returned only:
- `composition_id`

This is the correct ownership split.

Do not mutate W49 during automated browser work unless explicitly ordered.

Allowed by default:
- reload
- open/close UI
- inspect DOM/network

Not allowed without explicit user approval:
- save Dish
- select another Dish
- create Dish
- remove slot
- publish

---

# 9. LOCKED BUTTON / ACTION OWNERSHIP

This is the most important current product contract.

For a **resolved** menu row:

## Direct click on Dish name
-> open the existing finished shared Dish editor

## `⋯ -> Öppna rätt`
-> open the exact same existing finished shared Dish editor

## `⋯ -> Byt rätt`
-> open Rättbibliotek picker
-> choose another canonical `composition_id`

## `⋯ -> Ta bort från menyn`
-> remove only the canonical menu placement
-> never delete Dish / Components / library data

For unresolved imported text:
- no technical “Ej kopplad” status
- normal menu text
- guaranteed edit route is `⋯ -> Byt rätt`

Empty slots remain `—`.
Adding new slot content is later scope.

---

# 10. RÄTTBIBLIOTEK / SEARCH LOCK

Rättbibliotek is a **selector**, not another Builder.

Current accepted direction:
- search-driven
- do not dump the full library for an empty resolved search
- resolved `Byt rätt`: start with empty query and subtle `Byter: <current dish>`
- unresolved imported text may prefill search with the imported text
- `+ Skapa ny rätt` is secondary and must reuse shared Dish create flow

Search architecture was explicitly corrected:

`static/js/builder_composition_search.js`

is the shared canonical composition search runtime.

Both:
- real Builder
- Rättbibliotek

must use this same runtime.

Current canonical search behavior is name/id.

Hashtag/tag search is PARKED until implemented once in the canonical Builder search runtime.

Do not reintroduce a picker-specific matcher.

---

# 11. WHAT WENT WRONG IN THE LATEST MENYIMPORT WORK

A real-browser blocker appeared:

Clicking the resolved Dish did not reliably open the accepted shared Dish editor.

During attempts to fix this, Copilot took too much architectural ownership.

Bad turns included:
- routing existing-Dish open through a host that had also gained picker behavior
- mounting Builder modal partials/runtime directly into the week parent page
- causing the entire App Shell/week layout to collapse/compress visually
- creating additional picker/recovery surfaces
- following collateral effects into Offshore
- changing behavior merely because a test expected it

The visually broken week screenshot is a hard NO-GO.

Important lesson:

**Green tests do not override a visibly wrong real browser.**

The direct Builder-parent mount is rejected architecture.

---

# 12. HISTORICAL COMMITS THAT MATTER FOR THE FIX

The user correctly remembered that Menyimport -> shared Dish editing had already been built earlier.

Key historical integration chain:

`31592de6bd0e72702cc9a730afdaffdf7089d7e9`
`feat(builder): resolve imported menu rows in builder`

`eeb8ea296b2af21a8f9efc7c29a49476b798b919`
`feat(kommun): open imported menus in shared builder`

`dd7ffac54593ac114975d78a49b2f4c586caf4f0`
`feat(kommun): edit menu dishes in shared builder overlay`

`fd9ca3aa9668d91f9130ba19c44ce4deeeca67ca`
`style(kommun): flatten shared dish editor overlay`

`cbc2cef3c02c511570c529dc7c348bf5d6fedf15`
`fix(builder): preserve component return context`

Later accepted shared editor improvements:

`2e0793aa752b3cc8dcb844118e38529769f08af5`
`style(builder): stabilize shared editor shell and overview rail`

`1798dddff9e2a8146a0fa1945c836f281db6829b`
`refactor(builder): share calculation truth across editors`

`bda732af9893b591856b658f034fc6a5f2580589`
`style(builder): finish shared dish and component editors`

Historical important architecture at `dd7ffac`:

Menyimport parent
-> frosted overlay host
-> isolated iframe
-> `/builder-editor-host?composition_id=<id>`
-> shared existing Dish editor

The current fix must preserve later accepted editor improvements while restoring the correct integration seam.

Do **not** blindly checkout whole files from old commits.

---

# 13. CURRENT DIRTY WORKTREE / KNOWN UNRELATED FILES

At the verified snapshot state, Git status contained 20 modified tracked files + 6 untracked source files.

Known unrelated dirty files that must remain unstaged/preserved:
- `core/admin_repo.py`
- `scripts/seed_ostergarden_from_json.py`
- `scripts/seed_product2_e2e.py`

Never run `test_seed_product2_e2e.py` until it is separately audited; it has historically used `dev.db` directly.

Important current untracked files include:
- `static/js/builder_composition_search.js`
- `static/tests/builder_composition_search.test.js`
- `static/ui/admin_menu_import_week_actions.js`
- picker-related files from later experimentation

Do not assume “untracked” means “unwanted”.
The shared search runtime is accepted work and must be preserved.

---

# 14. TEST-ISOLATION INCIDENT CLOSED

A focused Menyimport test slice hit:

`sqlite3.IntegrityError UNIQUE constraint failed: tenants.name`

Root cause:
- a test helper created another app using the session DATABASE_URL
- the same temp DB was bootstrapped twice

Fix:
- test helper only
- dedicated isolated SQLite file/schema
- no production semantics changed

This isolation fix must be preserved.

Also, old Weekview test mutation of `dev.db` was already fixed earlier.

---

# 15. THE NEXT GATE — READ ONLY

The next chat should **NOT IMPLEMENT ANYTHING FIRST**.

Run a three-point forensic comparison:

A. historical working Menyimport shared-editor integration:
- `dd7ffac`
- `fd9ca3aa`
- `cbc2cef3`

B. later accepted shared editor finish:
- `2e0793aa`
- `1798ddd`
- `bda732`

C. current verified snapshot worktree

Goal:

Find the **first exact divergence** between the historical working existing-Dish open path and the current path.

Trace separately:
1. direct resolved Dish click
2. `⋯ -> Öppna rätt`
3. `⋯ -> Byt rätt`

The audit must identify the minimum patch without applying it.

Strong target:
- maximum 4 production files
- if more are required, STOP and explain
- Offshore must remain out of scope
- no new product surface
- no new modal
- no duplicate search/runtime
- no test-driven architecture changes

Expected end state of the audit:

`READY FOR MINIMAL DISH-OPEN PATCH DECISION`

Then the user/ChatGPT reviews the report before any implementation order.

---

# 16. COPILOT AUTHORITY RULE — NEW AND NON-NEGOTIABLE

The recent recovery became tangled because Copilot followed adjacent dependencies and started “making the whole system consistent”.

That is no longer acceptable during MVP closure.

Every implementation order must explicitly define allowed production files.

If Copilot concludes another production file is required:

**STOP AND REPORT.**

Do not:
- migrate another module
- create another route
- create another template
- create another runtime
- change a test and production code together just to get green
- refactor “while here”

Audit != implementation.

---

# 17. COMMIT STRATEGY

No commit for current Menyimport work yet.

Do not checkpoint until:
- correct button ownership works in the user's real browser
- Rättbibliotek visual behavior is accepted
- shared Dish editor opens correctly from both resolved entrypoints
- focused tests are green
- `git diff --check` clean
- current diff is understood and no recovery collateral remains

After acceptance, split into coherent commits rather than one giant recovery commit.

Possible logical grouping later:
1. canonical week/menu ownership and normal-flow cleanup
2. reusable canonical picker/search + slot actions
3. final integration/tests

Do not commit merely because automated browser proof passes.

---

# 18. RESPONSIVE / POLISH AFTER FUNCTIONAL CLOSURE

Once Menyimport desktop behavior is closed:
- global responsive shell pass
- iPad/tablet operational acceptance
- then mobile
- then consolidated visual polish

Do not mix responsive work into the current Dish-open recovery.

---

# 19. FIRST RESPONSE IN THE NEW CHAT

The next chat should say, in substance:

- handoff read
- stable committed checkpoint = `a0c84db...`
- current Menyimport work is uncommitted and local
- safety snapshot exists and current state was restored to it
- Weekview / Department / Kostbehov / Serveringsanpassningar desktop functional gates are closed
- active blocker is Menyimport existing-Dish open integration
- locked button matrix is understood
- next action is the **read-only three-point forensic comparison**
- no implementation before that report is reviewed

If the user pastes a Copilot report immediately, review it instead of sending another order.

---

# 20. ONE-LINE PROJECT STATE

**Kommun desktop core and Weekview are closed; Menyimport canonical selection/binding largely works, but existing-Dish open integration regressed during an over-broad recovery; the code is safely snapshotted and restored to the pre-restore snapshot state; next step is a read-only historical/current comparison, then one minimal Dish-open patch before responsive/pilot closure.**
