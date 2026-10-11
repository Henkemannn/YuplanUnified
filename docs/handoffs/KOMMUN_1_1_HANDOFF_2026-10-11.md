# KOMMUN 1.1 HARD HANDOFF — 2026-10-11

Status: ACTIVE HANDOFF  
Purpose: continue Yuplan Unified in a new ChatGPT window without losing the exact accepted state  
Development branch: `feat/planera-app-shell-2026-03-03`  
Documentation branch only: `handoff/kommun-1-1-2026-10-07`

> **DO NOT DEVELOP ON THIS HANDOFF BRANCH.**
>
> It is documentation only.
> Product development continues locally on `feat/planera-app-shell-2026-03-03`.

---

# 1. FIRST INSTRUCTION TO THE NEXT CHAT

Act as project manager / technical lead for Yuplan Unified.

Henrik owns product decisions.
GitHub Copilot in VS Code performs implementation.
ChatGPT holds product truth, architecture boundaries, acceptance state, and the next smallest safe gate.

Strict workflow:

**ONE ORDER -> ONE COPILOT REPORT -> REVIEW -> NEXT ORDER**

Every implementation order must start from:

```text
SESSION CONTEXT / AUTHORITY RESET

You are implementation Copilot.
ChatGPT is project lead / technical lead.
Work strictly: 1 order -> 1 report -> review -> next order.
Do not make architecture decisions outside the order.
Explicit DO NOT is absolute.
If a required production file is outside the allowlist: STOP AND REPORT.
Do not stage or commit without explicit order.
REUSE-BEFORE-BUILD is locked.
Preserve all accepted work outside the current gate.
```

Also include:

> You are implementing one approved seam, not owning the surrounding architecture. Any necessary change outside the explicitly allowed files is a STOP condition.

Rules:

- audit != implementation
- audits are read-only unless explicitly authorized
- no “while here” refactors
- no following side effects into Offshore or adjacent modules
- do not change production behavior just because an old test expects it
- real browser behavior is final UX truth
- protect pilot/user data
- no push unless Henrik explicitly asks

If Henrik pastes a Copilot report immediately, review that report instead of issuing another order.

---

# 2. LOCAL REPO STATE — AUTHORITY

Active development branch:

`feat/planera-app-shell-2026-03-03`

Latest accepted local HEAD:

`4efa33c0cb37b524c31569d8db2914dbead9019e`

`fix(menu): hydrate cook views from builder publication`

Previous accepted checkpoints directly relevant to the current end-to-end flow:

- `f23f96dc690f3c7933bdf5b201b0592e06c409e5` — `feat(admin): unify tenant user management`
- `8536658ec2f1a2870a5d68ca0052708a67cc97ff` — `feat(admin): finalize departments and service addon contract`
- `89a9b2c13283330f4905963d888b119a1cca6589` — `fix(admin): correct variable resident count semantics`
- `737c85c82b60ee4a93978ddc961f03dde8cb0ab3` — `fix(admin): show residence in department user labels`
- `221ce01b94814a82666b8d7ba6f1847ad3b7e8d7` — `fix(portal): land department users on overview`
- `3d559a3b483ed834bc220a2e343945e4a28be3ec` — `fix(menu): publish dynamic builder slots by position`
- `4efa33c0cb37b524c31569d8db2914dbead9019e` — `fix(menu): hydrate cook views from builder publication`

Important:

**These latest development checkpoints are LOCAL truth. No push was performed after the accepted menu checkpoints.**

Do not use GitHub remote development source as proof of current local implementation.

At the beginning of the next implementation/audit session, Copilot must run:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

Expected:

- branch = `feat/planera-app-shell-2026-03-03`
- HEAD = `4efa33c0cb37b524c31569d8db2914dbead9019e`

Expected unrelated dirty files only:

- `core/admin_repo.py`
- `scripts/seed_ostergarden_from_json.py`
- `scripts/seed_product2_e2e.py`

Never stage those without separate review/order.

---

# 3. PILOT DATA SAFETY — CRITICAL

Current MVP DB:

`instance/yuplan_mvp.db`

Current Builder DB:

`instance/builder_library.db`

Both are:

**PILOT / USER DATA**

Default automated proof may READ only.

Allowed by default:

- login
- reload
- navigate
- inspect DOM
- inspect route/view model
- query DB read-only

Not allowed without explicit order:

- create/delete/edit real departments/users
- publish/re-publish
- mutate publication pin/revision
- alter Builder rows
- save real Department Portal menu choices
- alter Linda's submitted choices
- reorder/delete menu rows

Human live acceptance may intentionally mutate data when that is the product test.

Canonical site used in current proof:

`ae4d40cd-a4f5-4acf-a59e-31d8272cb128`

---

# 4. CURRENT PRODUCT JOURNEY — A–Ö

The goal is not isolated feature polish.
We are proving the real operator journey:

**Admin/grunddata -> Meny -> Publicera -> Avdelning gör val -> Köket ser läget -> Planera räknar -> Produktionsunderlag**

Current state:

1. Admin / organisation / grunddata — **CLOSED**
2. Users / role binding / department linkage — **CLOSED**
3. Menu Builder/import/edit — **CLOSED for current MVP**
4. Publish real menu — **CLOSED**
5. Department Portal sees published week — **CLOSED**
6. Department makes menu choices — **CLOSED**
7. Department submits to kitchen — **CLOSED**
8. Kitchen Weekview sees submitted choices — **CLOSED**
9. Kitchen Menyöversikt/book popup sees published menu — **CLOSED**
10. Planera reads real Week 42 truth — **NEXT**
11. Planera calculates one real day correctly — **NEXT**
12. Produktionsunderlag — **NEXT**
13. Reload/relogin/persistence + role boundaries — **NEXT**
14. iPad/tablet operational acceptance — **NEXT / currently has login blocker**
15. Fresh Kommun pilot smoke — **NEXT**
16. Kommun 1.1 PILOT READY — **TARGET**
17. Offshore 1.0 closure
18. Yuplan 1.0 release gate

Do not reopen closed gates without a real regression.

---

# 5. ADMIN / DEPARTMENTS — CLOSED

Admin -> Avdelningar is Yuplan 1.0-ready.

Accepted:

- create/edit department
- residence creation/linkage
- `fixed` and `per_day_meal` resident-count modes
- specialkost/Kostbehov requirement groups
- Serveringsanpassningar/service addons
- reorder via canonical `departments.display_order`
- safe delete
- compact quick overview

User-facing terminology:

- residence selector = **Boende / enhet**
- department = **Avdelning**
- resident count = **Boendeantal**
- UI modes = **Fast antal** / **Varierar**

Variable-count rule:

- do not render internal fixed zero as user truth
- show `Varierar per dag/måltid`

Kostbehov truth:

`Normalkost = resident_count - effective special_diet_total`

Normalkost is derived, never manually stored.

100% Kostbehov is valid.
>100% is invalid.
No silent clamping.

---

# 6. REAL DEPARTMENT / PORTAL STATE — CLOSED

Real department restored and used in current proof:

Avdelning 2:
- id `ed1ae51e-3ae4-41c6-bf2e-f09c11db10f5`
- residence = **Kaktusen**
- residence id `dfef87cf-fe87-4c1e-8f5e-e58bf10b2151`
- resident count mode = `per_day_meal`

Department portal identity must show variable semantics, never fake `0 boende`.

Real `unit_portal` user:

**Linda Syrén**

Accepted portal behavior:

- login lands on `/ui/portal/department`
- direct authorized week route still works
- identity shows `Kaktusen · Varierar per dag/måltid`
- published Week 42 visible
- real menu choices completed
- portal status shows **Färdig**
- choices sent to kitchen

Department specialkost visible in the current pilot flow:

- Vegetarisk + Äggfri 1
- Glutenfri 2
- Timbal 3

Private admin notes must never leak to portal.

---

# 7. MENU / BUILDER — CURRENT 1.0 TRUTH

Earlier Menyimport/shared-editor work is no longer the active blocker.

Locked ownership:

Builder/domain owns:

- Components
- Dishes/Compositions
- canonical library
- Dish identity
- shared Dish editor
- shared Component editor
- canonical search semantics

Week/menu surface owns:

- week
- day
- row/slot placement
- action context

REUSE-BEFORE-BUILD remains locked.

Do not create:

- another Builder
- another Dish editor
- another Component editor
- duplicate search
- another modal architecture

The current MVP flow has passed live menu editing/import usage sufficiently to continue the A–Ö journey.

---

# 8. DYNAMIC SLOT PUBLICATION — CLOSED

Live publication originally failed with:

`unknown meal slot: slot_81d2ee77a00946c9970fba8f2568bc9d`

The Builder row itself was valid.

Important Builder truth:

- dynamic slot IDs are opaque and row-local
- display labels are free UI labels
- publication cannot infer semantics by parsing the label
- do not parse `menu_detail_id` for semantics

A proposed `canonical_meal_slot` redesign was explicitly abandoned and rolled back.

Do **not** resurrect it.

Accepted Kommun 1.0 compatibility seam:

commit:

`3d559a3b483ed834bc220a2e343945e4a28be3ec`

`fix(menu): publish dynamic builder slots by position`

For opaque dynamic slots only:

1 -> `lunch_alt1`
2 -> `lunch_alt2`
3 -> `dessert`
4 -> `dinner`

Source of position:

existing absolute within-day ordering encoded by `sort_order`.

Rules:

- known semantic meal slots pass through unchanged
- only opaque `slot_*` uses positional mapping
- gaps stay gaps
- no synthesized rows
- malformed/unsupported position fails closed

Real Week 42:

- publication succeeded
- status became Publicerad
- portal saw it

Sunday is a critical acceptance case:

- Alt1 exists
- Alt2 does NOT exist
- Dessert exists
- Dinner exists

No fake Alt2 may be created.

---

# 9. DEFERRED MENU MODEL — DO NOT BUILD DURING MVP FLOW

Longer-term desired product direction:

- neutral Slot 1, Slot 2, Slot 3...
- arbitrary display labels
- explicit selectable / non-selectable rows
- site/kitchen default selectable positions
- per-day exceptions
- possible future multiple selection groups

Example future intuition:

- Slot 1 + Slot 2 selectable
- Slot 3...100 read-only

This is deliberately deferred.

Current Portal selection model remains the existing Alt1/Alt2 contract.

Do not redesign Portal/Weekview/Planera now.

Do not add:

- `canonical_meal_slot`
- generic selection groups
- site menu settings
- new selection schema

until the real pilot flow is closed.

---

# 10. DEPARTMENT CHOICE -> KITCHEN — CLOSED

Henrik manually proved the real Week 42 path:

- Linda sees the published menu
- Linda completes all required menu choices
- Linda submits
- portal reports complete / sent to kitchen
- cook Weekview displays submitted choices as yellow markings

This proves the choice persistence chain through the kitchen overview.

Sunday missing Alt2 did not prevent completion.

---

# 11. COOK MENU READERS — CLOSED

Initial real bug:

Cook Weekview showed Linda's yellow choice markings, but:

- `Menyöversikt` displayed **Ingen meny ännu**
- the Weekview book/menu icon did not show Week 42 menu content

Read-only census proved:

Cook Menyöversikt:

`/ui/kitchen/menu`
-> `MenuServiceDB.get_week_view(...)`

Weekview book popup:

`WeekviewService.fetch_weekview(...)`
-> `WeekviewService._enrich_days(...)`
-> `current_app.menu_service.get_week_view(...)`

Both consumed the legacy menu reader.

Live Week 42 had:

- valid `commun_builder_publication_pins`
- Builder menu id `menu_cba1df57`
- Builder menu version 1
- projection status = ok
- projection rows = 27
- legacy `menus` row exists
- legacy `menu_variants` count = 0

Therefore legacy reader returned an empty menu.

Root cause classification:

**STALE LEGACY READER**

Accepted fix:

`4efa33c0cb37b524c31569d8db2914dbead9019e`

`fix(menu): hydrate cook views from builder publication`

Implementation principle:

- keep existing `MenuServiceDB.get_week_view(...)` return contract
- if a valid pinned Builder projection exists, hydrate the old week-view shape from it
- no DB backfill into `menu_variants`
- no caller rewrite
- if no Builder publication exists, preserve legacy behavior
- do not synthesize missing options

Files in checkpoint:

- `core/menu_service.py`
- `tests/core/test_commun_builder_publication.py`
- `tests/ui/test_kitchen_menu_overview.py`
- `tests/ui/test_weekview_site_overview_phase1.py`

Focused checkpoint proof:

3 passed.

Live browser acceptance after the fix:

- Menyöversikt Week 42 works perfectly
- Weekview book popup works perfectly
- Sunday correctly preserves missing Alt2

Treat this gate as CLOSED.

---

# 12. KNOWN TEST NOTE — DO NOT OVERCLAIM

A broader focused run around publication/read compatibility produced:

34 passed, 1 failed.

Failing test:

`tests/core/test_commun_builder_publication.py::test_publish_projection_failure_keeps_legacy_draft_and_no_pin`

The same test passes in isolation.

Interpretation:

- suite-order/state interaction exists
- it has not been fully root-caused
- do not falsely label it proven pre-existing or candidate-independent
- it is not a current live acceptance blocker

Investigate only if it becomes relevant to future work.

---

# 13. NEW LIVE BLOCKER — IPAD LOGIN VALIDATION

At the end of the session Henrik attempted to continue the cook flow on iPad.

Desktop cook login works.

On iPad the login form repeatedly says:

**“ange en e-postadress”**

The cook account uses an email address whose domain contains Swedish `ö`.

Important:

The exact stored email spelling must be confirmed from the local Admin/user record before any fix.

The earlier conversation suggested that HTML/Safari email validation of a Unicode/IDN domain may be involved, but this is only a hypothesis.

**DO NOT treat IDN/punycode as proven root cause yet.**

This is a real pilot issue because Yuplan is tablet-first.

---

# 14. FIRST GATE TOMORROW — IPAD LOGIN READ-ONLY CENSUS

Do not implement first.

The next Copilot order should be a narrow READ-ONLY census.

It must answer:

1. What exact email value is stored for the cook user?
2. Which login route is actually used?
3. Which template renders the email field?
4. What exact `<input>` attributes are present?
5. Is `type="email"` / pattern / JS validation preventing submit?
6. Does the iPad/browser stop the request before Flask receives it?
7. If the same Unicode email is POSTed directly, does server-side auth accept it?
8. Does auth normalize/casefold/domain-normalize emails today?
9. Are IDN/punycode libraries or helpers already present?
10. What is the smallest standards-compatible fix?
11. What tests already cover login validation and first-login flow?
12. Which exact production files would be required?

Safety:

- no user email mutation
- no password reset
- no auth migration
- no schema change
- no production implementation
- no staging/commit

Expected end state:

**READY FOR IPAD LOGIN FIX DECISION**

If Henrik chooses to proceed on desktop before this is fixed, keep this issue OPEN as a pilot blocker.

---

# 15. NEXT PRODUCT GATE AFTER LOGIN — PLANERA REAL WEEK 42

Once the intended test environment is available, continue the real A–Ö flow.

Login as cook and open:

**Planera — Week 42 / 2026**

Initially:

**READ / INSPECT ONLY. DO NOT SAVE.**

First acceptance question:

Does Planera consume the same real truth already proven upstream?

It must find:

- published Week 42 menu
- Avdelning 2 / Kaktusen
- Linda's submitted menu choices
- correct Sunday state with missing Alt2
- no stale legacy empty menu

If this initial view is wrong:

- census first
- trace route -> service -> adapter -> menu/choice sources
- reuse existing Builder publication and choice truth
- no Planera redesign

If it is right:

continue into one real day.

---

# 16. PLANERA CALCULATION ACCEPTANCE

The core Planera product truth remains:

**Normalkost = baseline. Kostbehov/specialkost = deviation.**

Conceptually:

`Normalkost = effective resident count - effective special_diet_total`

For one real day/meal, verify:

1. effective headcount
2. chosen menu option for each department
3. specialkost/Kostbehov groups
4. effective quantities after overrides
5. derived Normalkost
6. service-specific deviations
7. exact total per dish/component path
8. no double-counting of composite requirements
9. no fake zero for variable-count departments
10. no invented menu option where slot is absent

Planera is the primary production workflow.

Weekview is overview/facit/fallback.

Do not create a second calculation engine in Weekview or templates.

---

# 17. PRODUKTIONSUNDERLAG — AFTER PLANERA

After the Planera day calculation is accepted, verify Produktionsunderlag.

It should operationally answer:

- what is cooked
- how many normal portions
- which Kostbehov/special adaptations
- how many of each
- department/service context
- preparation/production basis that another cook can follow

The output must derive from the same accepted Planera truth.

No manual parallel totals.

If production basis differs from Planera:

trace the adapter/projection seam rather than patching display numbers.

---

# 18. RELOAD / RELogin / PERSISTENCE GATE

After Planera + Produktionsunderlag work:

prove persistence.

At minimum:

- reload same page
- log out/in
- admin view
- unit_portal view
- cook view
- Week 42 menu unchanged
- Linda's choices unchanged
- Planera truth unchanged
- no role leaks
- no dependence on transient in-memory browser state

This is required before fresh pilot smoke.

---

# 19. TABLET / RESPONSIVE ACCEPTANCE

Tablet is a primary Yuplan environment.

Broad responsive work was intentionally parked while desktop functionality closed.

After the A–Ö functional path is proven:

1. shared App Shell / breakpoint review
2. iPad/tablet operational pass
3. module-level fixes
4. iPhone/mobile pass
5. consolidated polish

Do not mix broad responsive cleanup into one narrow functional bug.

Current iPad login failure is an operational auth/input bug and should be fixed narrowly.

---

# 20. ENCODING ISSUE — PARKED

Visible strings include examples such as:

- `Centralk?ket`
- `Anv?ändare`

Other Swedish strings render correctly:

- Köttbullar
- Kvällsmat
- Återgå
- etc.

Therefore:

not proven global UTF-8/font failure.

Likely individual damaged strings/data.

Future small cleanup:

- search exact broken values at source
- fix data/source text
- no template sanitizer
- do not block Planera flow on this unless it interferes with identity/login

---

# 21. COMMIT / PUSH RULES

Current accepted local HEAD is already checkpointed at:

`4efa33c0cb37b524c31569d8db2914dbead9019e`

No push was performed.

Do not push unless Henrik explicitly requests it.

For each future accepted fix:

1. implementation
2. focused tests
3. Henrik live browser acceptance
4. stage only accepted files
5. checkpoint commit
6. verify unrelated dirty work remains unstaged
7. no push

---

# 22. WHAT NOT TO REOPEN

Unless a proven pilot blocker requires it, do not reopen:

- Admin Department UX
- service addon schema
- portal landing
- dynamic slot publication architecture
- cook menu-reader architecture
- broad Builder redesign
- generic menu selection groups
- `canonical_meal_slot`
- Offshore
- Home
- Hotel/Bankett
- Recipe expansion
- broad dead-code cleanup

Current mission is pilot closure, not architecture perfection.

---

# 23. MACRO ROADMAP AFTER CURRENT PILOT

Product path:

**Kommun pilot -> paying-user proof -> Offshore 1.0 -> Recipe/Production Needs -> Purchasing/Cost -> Hotel/Bankett -> shared platform services -> AI expansion -> Yuplan Home**

The immediate objective is to finish the real Kommun production loop before broadening scope.

Commercial/product direction remains:

- prove real paying kitchen value first
- get Kommun pilot operational
- then reuse the shared platform architecture in Offshore and later verticals

---

# 24. EXACT FIRST RESPONSE EXPECTED IN THE NEW CHAT

The new ChatGPT window should say, in substance:

- handoff read
- local development branch is `feat/planera-app-shell-2026-03-03`
- accepted local HEAD is `4efa33c0...`
- remote development source may lag; local Copilot state is authoritative
- Admin, menu publication, Department Portal choice flow, kitchen choice visibility, Menyöversikt and book popup are CLOSED
- real Week 42 is the accepted live proof week
- Sunday missing Alt2 is an important invariant
- current newly discovered blocker is iPad login validation for the cook account
- root cause is NOT yet proven
- first action is a narrow read-only auth/input-validation census
- after that, continue real Week 42 into Planera and Produktionsunderlag
- no broad implementation before the report is reviewed

If Henrik instead opens tomorrow by saying desktop/iPad login now works, do not force an unnecessary audit. Continue directly to the real Week 42 Planera acceptance and keep any unresolved tablet issue only if it still exists.

---

# 25. ONE-LINE CURRENT STATE

**The real Kommun journey is now proven from Admin and Builder through publication, Department Portal selection/submission and kitchen menu/choice visibility; latest accepted local HEAD is `4efa33c0...`; the next unresolved live issue is iPad login validation for the cook identity, then the project continues directly into real Week 42 Planera -> Produktionsunderlag -> persistence -> tablet smoke -> Kommun 1.1 pilot readiness.**
