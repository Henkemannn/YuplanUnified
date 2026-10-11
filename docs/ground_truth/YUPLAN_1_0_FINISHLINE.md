Status: LOCKED
Last reviewed: 2026-10-11

# Yuplan 1.0 Finishline

## Current Phase

Active phase:

**Kommun 1.1 — finish the real A–Ö operational journey through Planera and Produktionsunderlag, then tablet/responsive acceptance and fresh pilot smoke.**

The broad Builder/Planera architecture is not being reopened.

The previously active Menyimport/shared-editor blocker is closed for Yuplan 1.0. The current real flow has now been proven through:

**Admin/grunddata -> Meny -> Publicera -> Avdelning gör val -> Köket ser val + meny**

The next product gate is **Planera**.

There is one newly discovered tablet login blocker before/alongside Planera acceptance:

- a cook user whose email contains a Swedish character in the domain is rejected by the iPad login form with “ange en e-postadress”
- exact root cause is not yet proven
- treat this first as a narrow read-only login/input-validation census
- do not assume IDN normalization or change stored identities until proven

## Current local committed checkpoint

Active development branch:

`feat/planera-app-shell-2026-03-03`

Latest accepted local checkpoint:

`4efa33c0cb37b524c31569d8db2914dbead9019e`

`fix(menu): hydrate cook views from builder publication`

Previous accepted checkpoints relevant to the current A–Ö flow:

- `f23f96dc690f3c7933bdf5b201b0592e06c409e5` — `feat(admin): unify tenant user management`
- `8536658ec2f1a2870a5d68ca0052708a67cc97ff` — `feat(admin): finalize departments and service addon contract`
- `89a9b2c13283330f4905963d888b119a1cca6589` — `fix(admin): correct variable resident count semantics`
- `737c85c82b60ee4a93978ddc961f03dde8cb0ab3` — `fix(admin): show residence in department user labels`
- `221ce01b94814a82666b8d7ba6f1847ad3b7e8d7` — `fix(portal): land department users on overview`
- `3d559a3b483ed834bc220a2e343945e4a28be3ec` — `fix(menu): publish dynamic builder slots by position`
- `4efa33c0cb37b524c31569d8db2914dbead9019e` — `fix(menu): hydrate cook views from builder publication`

Important:

**The latest development commits above are local truth. No push has been performed after the accepted checkpoints in this flow. Do not use the remote development branch as proof of current local source.**

Before implementation work in a new session, Copilot must report:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

Expected local HEAD:

`4efa33c0cb37b524c31569d8db2914dbead9019e`

Expected unrelated dirty files only:

- `core/admin_repo.py`
- `scripts/seed_ostergarden_from_json.py`
- `scripts/seed_product2_e2e.py`

Never stage those files without separate review/order.

## Non-negotiable workflow

**ONE ORDER -> ONE COPILOT REPORT -> REVIEW -> NEXT ORDER**

For every implementation order:

> You are implementing one approved seam, not owning the surrounding architecture. Any necessary change outside explicitly allowed files is a STOP condition.

Also:

- audits are read-only unless explicitly authorized
- no “while here” refactors
- no collateral migration into Offshore or adjacent modules
- a failing test is evidence, not automatic authority to rewrite production behavior
- real Firefox/iPad/browser behavior is final UX truth
- protect pilot/user data
- REUSE-BEFORE-BUILD is locked

## Current pilot data safety

Primary MVP DB:

`instance/yuplan_mvp.db`

Builder menu DB:

`instance/builder_library.db`

Both are **PILOT / USER DATA**.

Automated browser proof must not mutate the real pilot data unless explicitly ordered.

Read-only by default:

- reload
- login
- inspect
- query
- route/view-model proof

Do not automatically:

- create/delete departments
- publish/re-publish
- change menu rows
- submit department choices
- alter publication pins
- mutate Builder rows

Human manual acceptance may intentionally mutate data when the test itself requires it.

Canonical live site used in current proof:

`ae4d40cd-a4f5-4acf-a59e-31d8272cb128`

## Closed Kommun gates

### 1. Admin / organisation / grunddata — CLOSED

Accepted for current Kommun 1.0:

- create/edit departments
- residence linkage
- fixed and per-day/meal resident-count semantics
- Kostbehov / requirement groups
- Serveringsanpassningar / service addons
- ordering
- safe delete
- quick overview
- variable-count semantics without fake zero

User-facing terms remain:

- Boende / enhet
- Avdelning
- Boendeantal
- Fast antal
- Varierar

Variable departments must never render an internal fixed zero as user truth.

### 2. Admin -> Användare — CLOSED

Tenant/site user management is accepted.

Department affiliation labels:

- with residence: `<residence> – <department>`
- without residence: department only
- no site fallback prefix

A real `unit_portal` user was created and used in live acceptance.

### 3. Department Portal landing / identity — CLOSED

Accepted:

- `unit_portal` login lands on `/ui/portal/department`
- direct authorized week URL remains accessible
- variable departments render `Varierar per dag/måltid`
- never fake `0 boende`
- empty state for no published menus is correct

### 4. Menu / Builder editing + import — CLOSED for current 1.0 flow

The earlier Menyimport/shared Dish-editor recovery is no longer the active blocker.

Current 1.0 assumptions:

- Builder/domain owns canonical dishes/components/compositions
- week/menu surface owns placement context
- shared editor/search is reused
- no second Builder implementation
- imported/canonical menu editing has passed the accepted live workflow

Future menu-model redesign is explicitly deferred.

### 5. Publication — CLOSED

Real Week 42 / 2026 publication initially failed on opaque dynamic Builder slot IDs.

Accepted compatibility fix:

`3d559a3b483ed834bc220a2e343945e4a28be3ec`

`fix(menu): publish dynamic builder slots by position`

For opaque dynamic slots only, absolute within-day position maps for Kommun 1.0 compatibility:

1 -> `lunch_alt1`
2 -> `lunch_alt2`
3 -> `dessert`
4 -> `dinner`

Important:

- semantic slots already known pass through unchanged
- display labels are not parsed
- menu_detail_id is not parsed for semantics
- gaps are preserved
- unsupported/malformed positions fail closed
- Sunday Week 42 correctly has Alt1 + Dessert + Dinner and no synthesized Alt2

Real browser acceptance:

- Week 42 published successfully
- status changed to Publicerad
- Department Portal could see it

### 6. Department menu choice + submit — CLOSED

Real department user:

- opened published Week 42
- completed required choices
- submitted choices to kitchen
- portal showed Färdig / choices sent

Sunday with missing Alt2 did not block completion.

### 7. Kitchen sees department choices — CLOSED

A real cook user was created.

In Weekview Week 42:

- submitted department choices appear as yellow markings
- choice truth survived from portal to kitchen view

### 8. Cook menu readers — CLOSED

Initial live bug:

- Weekview choice markings were visible
- Menyöversikt said “Ingen meny ännu”
- book/menu icon showed no menu

Root cause:

- both cook surfaces ultimately read `MenuServiceDB.get_week_view(...)`
- that reader still consumed legacy `menus + menu_variants`
- the Week 42 legacy menu row existed but `menu_variants` count was 0
- the Builder publication pin and projection were valid

Accepted fix:

`4efa33c0cb37b524c31569d8db2914dbead9019e`

`fix(menu): hydrate cook views from builder publication`

Contract:

- valid pinned Builder projection is the menu-content source
- return shape of `MenuServiceDB.get_week_view(...)` remains compatible with existing consumers
- no DB backfill into `menu_variants`
- legacy behavior remains fallback when no Builder publication exists
- no fake Sunday Alt2

Real browser acceptance:

- cook Menyöversikt shows Week 42 menu correctly
- Weekview book/menu popup shows the menu correctly
- Sunday gap is correct

## Known test note

During publication/read-compatibility work, a broader focused slice repeatedly hit:

`test_publish_projection_failure_keeps_legacy_draft_and_no_pin`

as a suite-order/state failure.

The same test passes in isolation.

Do not claim it is fully root-caused. It is known test-state contamination evidence, not a current live product blocker.

Investigate only if it becomes relevant to the next gate.

## Current A–Ö journey

Status now:

1. Admin / organisation / grunddata — **CLOSED**
2. Users / roles / department linkage — **CLOSED**
3. Menu Builder/import/edit — **CLOSED for current MVP**
4. Publish real menu — **CLOSED**
5. Department Portal sees published week — **CLOSED**
6. Department chooses menu — **CLOSED**
7. Department submits to kitchen — **CLOSED**
8. Kitchen Weekview sees choices — **CLOSED**
9. Kitchen Menyöversikt/book icon sees published menu — **CLOSED**
10. Planera reads real Week 42 truth — **NEXT**
11. Planera day calculation: chosen dish + headcount + Kostbehov/Normalkost — **NEXT**
12. Produktionsunderlag — **NEXT**
13. Reload/relogin/persistence and role-boundary smoke — **NEXT**
14. Tablet/iPad operational acceptance — **NEXT / partially blocked by login validation**
15. Fresh Kommun pilot smoke — **NEXT**
16. Declare Kommun 1.1 PILOT READY — **TARGET**
17. Return to Offshore 1.0 closure
18. Yuplan 1.0 release gate

## Next gate: iPad login validation census

New live issue:

The cook login works on desktop, but on iPad the login form repeatedly says to enter an email address for the cook identity whose email contains `ö` in the domain.

This has **not** yet been root-caused.

Do not immediately:

- rename the user
- change auth storage
- rewrite login
- add ad-hoc punycode logic
- alter browser validation globally

First order must be READ ONLY and answer:

1. What exact email is stored for the cook user?
2. What exact login template/input attributes are rendered?
3. Is the browser blocking form submission before the request reaches Flask?
4. What does Safari/iPad accept/reject for this exact value?
5. Does server-side auth accept the Unicode address if submitted without browser validation?
6. Is normalization currently performed anywhere?
7. What is the narrowest standards-compatible fix?
8. What tests already cover login email syntax and tablet/browser behavior?

The product requirement is simple:

**A valid Yuplan account must be able to log in from supported iPad/tablet UI.**

Do not over-design identity architecture during this gate.

If the user instead chooses to continue Planera on desktop first, keep the iPad login issue open as a pilot blocker.

## Then: Planera real-week acceptance

Once the user can continue in the intended environment, open Planera for real Week 42 and initially **do not save anything**.

The first Planera acceptance asks whether it:

- finds the published Week 42 menu
- sees Avdelning 2 / Kaktusen
- sees the submitted department menu choices
- preserves Sunday with no Alt2
- consumes Builder publication truth rather than stale legacy menu content

If wrong:

- census first
- identify exact reader/adapter seam
- no broad Planera redesign

If correct:

continue into one real day and verify:

- effective resident count
- chosen menu option
- Kostbehov quantities
- derived Normalkost
- service-specific deviations
- exact production quantities per dish

Then verify Produktionsunderlag.

## Planera product truth

Locked principle:

**Normalkost is the single source of production baseline; specialkost/Kostbehov is the deviation.**

Conceptually:

`Normalkost = resident_count - effective special_diet_total`

Planera is the primary production-calculation workflow.

Weekview is overview/facit/fallback and must not become a second production engine.

Menu publication is input truth.
Department choices are demand truth.
Planera combines those truths into operational production quantities.

Do not duplicate calculations in UI templates.

## Deferred menu-model direction — DO NOT BUILD NOW

The current positional compatibility adapter is accepted for Kommun 1.0.

Longer-term desired Builder model:

- neutral menu slots (Slot 1, Slot 2, ...)
- free display labels
- explicit selectable / non-selectable rows
- site/kitchen defaults for commonly selectable positions
- optional per-day exceptions
- possible future selection groups

Do not resurrect `canonical_meal_slot`.

Do not redesign Portal/Weekview/Planera around generic selection groups during current MVP closure.

## Parked UI/data cleanup

Visible encoding issues remain:

- site label can show `Centralk?ket`
- sidebar can show `Anv?ändare`

Because Swedish characters render correctly elsewhere, treat these as individual corrupted strings/data, not proven global UTF-8 failure.

Fix later at source; do not add template sanitizers.

## Responsive / tablet direction

Tablet-first remains a core product requirement.

After A–Ö functional closure:

1. shared App Shell / breakpoint pass
2. iPad/tablet operational acceptance across core Kommun flow
3. module-level responsive fixes
4. iPhone/mobile pass
5. consolidated visual polish

Do not mix broad responsive redesign into functional bug fixes.

The new iPad login validation issue is an operational blocker, not a request for a full responsive pass.

## Remaining path to Kommun pilot readiness

1. Resolve/understand iPad cook-login validation.
2. Open real Week 42 in Planera.
3. Verify Planera consumes published menu + submitted choices.
4. Verify one-day calculations end-to-end.
5. Verify Produktionsunderlag.
6. Verify reload/relogin/persistence.
7. Verify role boundaries with real admin/unit_portal/cook accounts.
8. Run global iPad/tablet operational pass.
9. Fix only pilot-blocking responsive defects.
10. Run fresh Kommun pilot smoke from Admin -> Kitchen production basis.
11. Declare Kommun 1.1 PILOT READY.
12. Return to Offshore 1.0 closure.
13. Finish Yuplan 1.0 release gate.

## After Kommun pilot

Planned macro path:

**Kommun pilot -> paying-user proof -> Offshore 1.0 -> Recipe/Production Needs -> Purchasing/Cost -> Hotel/Bankett -> shared platform services -> AI expansion -> Yuplan Home**

Do not let future-platform work delay the first real Kommun pilot.

## One-line finishline state

**The real Kommun flow is proven from Admin and Builder through publication, Department Portal choices and kitchen visibility; both cook menu readers now consume the published Builder truth; next is the narrow iPad login-validation blocker and then real Week 42 Planera -> Produktionsunderlag acceptance, followed by tablet smoke and Kommun pilot readiness.**
