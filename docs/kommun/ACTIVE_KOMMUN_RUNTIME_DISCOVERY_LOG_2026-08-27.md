# Active Kommun Runtime — Discovery & Convergence Log

**Date:** 2026-08-27  
**Branch:** `feat/planera-app-shell-2026-03-03`  
**Baseline before this log:** `b635443` — `feat(portal): canonicalize publication and department menu choices`

## Purpose

This is a working discovery/convergence log for the **currently active Kommun runtime**.

It records what has been verified in the active codebase and the project-lead decisions made from that evidence before the next implementation ticket.

It is **not** a replacement for the LOCKED Ground Truth documents. If the ongoing read-only audit changes or sharpens any conclusion below, the final architectural decision must be reflected in the relevant Ground Truth/decision log before implementation moves beyond the seam.

---

## 1. Major discovery: active Kommun is a composite runtime

The currently active Kommun product is not implemented in one isolated module. Runtime responsibility is spread across multiple active layers, including the municipal module registration and shared/core UI and service paths.

The practical mental model is:

```text
                    YUPLAN AUTH
             users / tenant / site / role
                       |
         +-------------+-------------+
         |             |             |
       ADMIN          KITCHEN      UNIT_PORTAL
         |             |             |
         |             |             +-- existing account role
         |             |                 and credentials flow
         |             |
         |             +-- Weekview
         |                 specialkost
         |                 resident counts
         |                 operational Alt2
         |                 menu presentation
         |                 |
         |                 +-- Planera V1
         |
         +-- user/admin configuration
             departments
             sites
             diets
             residents
             menu administration
             information
```

This means Kommun must be finished by **converging existing active seams**, not by rebuilding the module from scratch.

---

## 2. Existing `unit_portal` account flow is real

The active platform already has real `User` accounts and an existing application role named:

```text
unit_portal
```

Admin/superuser can already create users with credentials and select `unit_portal` as the role. The existing user administration handles real platform users, password hashing/reset and normal authentication.

Therefore the Kommun 1.0 portal account concept already exists:

```text
Admin
  -> creates user
  -> role = unit_portal
  -> gives department credentials
```

### Missing seam

The incomplete part is the authoritative relationship:

```text
unit_portal User
        ->
which Department?
```

The active `User` model does not currently provide a verified canonical `Department` binding.

An older `unit_id` exists, but **Unit and Department are not to be treated as the same concept without repository evidence**.

### Decision

Do **not** create a second authentication system for Avdelningsportal.

Reuse Yuplan's existing platform authentication and finish the missing department authorization/binding seam.

---

## 3. Generic membership architecture is paused

A previous PF-3 direction considered introducing a generic user-to-department membership table.

That implementation is now **paused**.

The current Kommun business model appears simpler:

> For Kommun 1.0, one `unit_portal` account represents one department.

The active deep audit must verify that this model fits all existing runtime behavior before schema implementation is chosen.

### Current preferred direction, pending audit confirmation

```text
User(role = unit_portal)
        -> one Department
        -> Department.site_id
        -> Site.tenant_id
```

Server-side validation must ensure the authenticated user's tenant matches the Department's actual Site/Tenant chain.

### Guardrail

Do not repurpose `User.unit_id` as `Department` merely because it already exists.

Do not introduce many-to-many membership, department selectors or generalized organization membership architecture unless current runtime evidence proves they are required.

---

## 4. Two active Avdelningsportal generations exist

A major runtime discovery is that two portal generations appear to remain registered/active at the same time.

### Older portal generation

Representative routes include:

```text
/ui/portal/week
/ui/portal/day/...
```

This path is associated with the older Kommun UI flow and uses active Kommun services such as Weekview/MenuService and historical/session-based department scope.

Parts of this path may already have been modernized by PF-2, including use of the dedicated menu-choice truth.

### New canonical portal generation

Representative routes include:

```text
/ui/portal/department/week
/portal/department/week
/portal/department/menu-choice/change
```

This path is the current canonicalization target and already uses the new seams established by PUB-1/PF-1/PF-2.

### Decision

**Do not build a third portal.**

The project must converge the two existing portal generations into one canonical Avdelningsportal.

Before decommissioning the older path, compare functionality and preserve any useful behavior/UX that exists only there.

---

## 5. Canonical portal data seams already established

The following milestone is complete and frozen at baseline `b635443`:

### PUB-1

Published Kommun menu projection is frozen as an immutable publication snapshot.

Changing a live underlying Dish/Composition after publication must not mutate the already-published menu. Republish/new publication is required to expose the change.

### PF-1

The new Avdelningsportal reads published menu presentation through the canonical Builder publication path rather than falling back to legacy menu truth.

### PF-2

Explicit department menu choice uses dedicated storage:

```text
department_menu_choices
```

This is separate from kitchen operational Alt2/Weekview state.

### Locked separation

```text
Avdelningsportal explicit Alt1/Alt2 choice
        -> department_menu_choices

Kitchen operational Alt2 / Weekview
        -> Weekview operational truth
```

These concepts must never be merged to make tests or UI behavior easier.

---

## 6. Kitchen Weekview remains an active Kommun core

The existing Kommun Weekview is still part of the active product and carries important operational data and workflow, including department/day/meal context, resident counts, dietary/specialkost data and operational menu state.

### Product decision

Do not replace the existing simple Kommun kitchen Weekview with a Builder-oriented UI.

The intended working model remains:

```text
Menu administration / Builder
        -> Published Menu
        -> existing/simple Kommun Weekview
        -> Planera / production
```

Kitchen staff normally **consume** an already-decided/published menu. They are not expected to work as menu authors in Builder.

---

## 7. Builder publication is already partially integrated with Weekview

The active code contains a Builder-reader integration for the existing Weekview, including the feature path associated with:

```text
commun.builder.reader_v0
```

Conceptually it allows:

```text
existing Weekview VM
        +
canonical Builder publication
        ->
same kitchen weekly grid with canonical menu presentation
```

This closely matches the desired Kommun architecture.

### Open verification

The current audit must still establish the effective pilot/runtime state of the feature flag and identify where legacy `MenuService` remains the actual menu source.

Do not assume all Kommun sessions are already cut over to Builder publication merely because the integration code exists.

---

## 8. `MenuService` is still active and must not be ripped out blindly

The active Kommun runtime remains hybrid. `MenuService` still participates in currently registered menu/UI flows, while Builder publication is becoming the canonical menu baseline in newer seams.

Current convergence model:

```text
           MenuService
               |
        existing consumers
               |
            Weekview

Builder -> Publication
               |
        canonical consumers
               |
            Weekview / Portal
```

### Decision

Do not perform a broad `MenuService` deletion/refactor.

Move consumers seam-by-seam to canonical publication where the contract is ready, preserve working behavior, and retire obsolete paths only after parity/evidence.

---

## 9. Planera V1 remains the active Kommun production path

The current Kommun operational workflow still uses Planera V1 for production planning.

Planera 2.0 is the future generic production engine and is **not** to replace the current production path before contracts, shadow execution and parity are established.

### Locked migration direction

```text
Today:
Weekview / Kommun context
        -> Planera V1

Target:
Published Menu
+ Kommun Business Context / Effective Demand
        -> Planera 2.0 shadow
        -> parity
        -> cutover only after accepted parity
```

### Decision

Do not redesign Planera during portal convergence.

---

## 10. Department Portal and Kitchen UI are separate workspaces

The Department Portal is a communication/experience layer for department staff.

Kitchen operational surfaces belong to kitchen/admin users.

### Current product decision

A normal `unit_portal` user should not be given portal navigation into kitchen operational Weekview or kitchen production reports merely because historical routes/role mappings allow it.

Conceptually:

```text
UNIT_PORTAL
- published menu
- own explicit menu choices
- relevant department information
- read-only dietary/resident context where appropriate
- communication/info

NOT
- kitchen Planera
- kitchen operational Weekview
- kitchen production reports
- Builder
```

Admin access to operational/admin surfaces remains separate from the department user's portal experience.

---

## 11. Immediate project decision: PF-3B implementation is paused

Do not implement the previously drafted generic PF-3B membership ticket yet.

The next gate is a read-only runtime audit covering:

1. complete `unit_portal` account creation/login/redirect flow
2. old `/ui/portal/week` generation
3. new `/ui/portal/department/week` generation
4. feature parity between them
5. all active navigation/entrypoints
6. exact User/Unit/Department/Site/Tenant relationships
7. tenant/site/department isolation
8. current tests and missing coverage
9. minimum-risk convergence plan

No code changes should occur before that report is reviewed by the project lead.

---

## 12. Current working Kommun convergence order

The finishline is now better expressed as:

```text
1. Active Kommun runtime inventory
   -> IN PROGRESS / deep audit underway

2. Unit Portal consolidation
   -> existing account model
   -> authoritative Department binding
   -> deterministic portal landing
   -> real tenant/site authorization

3. Portal convergence
   -> compare old vs new
   -> preserve useful unique functionality
   -> one canonical portal implementation
   -> redirect/decommission obsolete route(s)

4. Builder -> Weekview menu convergence
   -> preserve existing kitchen grid
   -> canonical Published Menu becomes menu baseline

5. Define Planera 2.0 Kommun production contracts

6. Kommun -> Planera 2.0 shadow/parity

7. Cut over only after accepted parity

8. iPad/auth/print/operational pilot polish

9. Full E2E

10. Kommun 1.0 Ready for Pilot

11. Return main product focus to Offshore 1.0
```

---

## 13. Open questions for the active audit

The read-only audit must resolve these before the next implementation ticket:

- Where exactly does `unit_portal` land after login today?
- Was there an existing but incomplete Department binding mechanism?
- What, if anything, does `User.unit_id` currently mean in live Kommun runtime?
- Which portal generation is reachable through normal navigation today?
- Which useful features exist only in `/ui/portal/week` or `/ui/portal/day/...`?
- Which parts of the old portal already consume `department_menu_choices`?
- What is the effective runtime state of `commun.builder.reader_v0`?
- Where does active Kommun still rely on `MenuService` for menu truth?
- What is the smallest safe one-user/one-department schema change if no existing relation can be reused?
- Which old portal routes/files can eventually be redirected or retired without losing behavior?

---

## 14. Guardrails until audit acceptance

Until the current convergence audit has been reviewed:

- no PF-3 implementation
- no new membership architecture
- no third portal
- no broad auth refactor
- no replacement of Kommun Weekview
- no Planera redesign
- no broad `MenuService` removal
- no Builder changes
- no reopening PUB-1/PF-1/PF-2 without a verified regression
- no merging department explicit choice with kitchen operational Alt2

The objective is **convergence of working active Kommun functionality**, not a rewrite.
