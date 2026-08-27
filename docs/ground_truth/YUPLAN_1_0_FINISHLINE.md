Status: LOCKED
Last reviewed: 2026-08-27

# Yuplan 1.0 Finishline

## Current Phase
The shared Builder/Menu/Offshore seam was accepted and frozen on 2026-08-27 after live Workspace/Host/Work Menu parity verification.

Active phase: Portal Foundation / Avdelningsportal canonical-path consolidation for Yuplan Kommun 1.0.

Broad Builder/Menu MVP work is closed. Only pilot-blocking regressions may reopen the seam before Kommun 1.0 Ready for Pilot.

## Already Established
- Builder is the canonical knowledge source.
- Components -> Dishes/Compositions -> Menus -> Published Menu.
- Canonical standalone Dish/Component editor works outside the full Builder Workspace.
- Shared Builder Component Library runtime is the intended Workspace/Host path; embedded business-module hosts stay thin.
- Cook COW isolation works for Dish and Component.
- Custom Dish menu name backend and UI are complete.
- Work Menu resolves a cook's effective scoped Dish.
- Work Menu can choose or create a real canonical Builder Dish and store canonical composition identity.
- Ghost demo Builder IDs and old-modal fallback cleanup are complete.
- Scope-aware Builder writes require real ActorContext and explicit canonical scope.
- Offshore demo/provisioning Builder bootstrap uses a real principal in the target tenant; fabricated or borrowed cross-tenant principals are forbidden.
- Live Offshore Work Menu parity is accepted: existing canonical Dish selection, reload persistence, create Dish -> Component -> Work Menu, canonical edit refresh, and reset to published baseline all passed manual E2E verification on 2026-08-27.
- Legacy unscoped Builder data is historical/dev compatibility data, not the intended fresh-tenant model.

## Builder/Menu/Offshore Freeze
- A fresh tenant must start with explicit scope from its first canonical write.
- Legacy scope repair must remain provenance driven; do not guess tenant ownership.
- Temporary missing-scope read compatibility may remain while legacy data is contained or migrated.
- Legacy dev-data cleanup is not a reason to redesign Builder for new tenants.
- Do not add broad Builder/Menu MVP features before Kommun 1.0 Ready for Pilot.
- Reopen this seam only for a concrete pilot-blocking regression or a deliberate Ground Truth decision change.

## Next Major Milestone
Yuplan Kommun 1.0 - Ready for Pilot.

Order:
1. Builder/Menu/Offshore seam freeze - COMPLETE (2026-08-27).
2. Ground Truth / Planera 2.0 Architecture Lock - COMPLETE.
3. Portal Foundation / Avdelningsportal canonical-path consolidation - ACTIVE.
4. Define and verify Planera 2.0 production contracts needed for Kommun integration.
5. Kommun -> Planera 2.0 shadow/parity integration.
6. Planera 2.0 becomes Kommun production calculation after parity acceptance.
7. Finish Avdelningsportal.
8. iPad/auth/print/operational polish.
9. Full Kommun end-to-end acceptance: Builder -> Published Menu -> Department Portal/menu choice -> effective demand/requirements -> Planera 2.0 -> production/packing output.
10. Kommun 1.0 Ready for Pilot.
11. Return main development focus to Offshore 1.0.

Do not list H3 Offshore Bibliotek as a blocker for Kommun launch.

## Freeze Point
Builder/Menu/Offshore broad MVP work is frozen as of 2026-08-27. Scope integrity remains a platform invariant, and legacy-scope debt may be contained or repaired without reopening Builder product scope. Only pilot-blocking defects may reopen the seam before Kommun 1.0 Ready for Pilot.
