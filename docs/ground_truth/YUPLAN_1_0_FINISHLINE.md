Status: LOCKED
Last reviewed: 2026-08-27

# Yuplan 1.0 Finishline

## Current Phase
Close and freeze the shared Builder/Menu/Offshore seam. Current hardening focus is Builder runtime parity and tenant/scope integrity, not new Builder feature work.

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
- Legacy unscoped Builder data is historical/dev compatibility data, not the intended fresh-tenant model.

## Immediate Remaining Builder/Menu Seam
1. Prevent current scope-aware write paths from creating new unscoped canonical Components/Compositions.
2. Verify real tenant/user ActorContext propagation through Builder, menu-context and Offshore paths.
3. Resolve Offshore demo/provisioning actor bootstrap without fabricating a principal or borrowing one from another tenant.
4. Repair or quarantine legacy scope data only where provenance is safe.
5. Move missing-scope reads to deny-by-default only after migration/parity.
6. Run live Workspace/Host/Work Menu parity gate.
7. Fix only pilot-blocking Builder regressions.
8. Freeze broad Builder/Menu MVP work.

A fresh tenant must start with explicit scope from its first canonical write.
Legacy dev-data cleanup is not a reason to redesign Builder for new tenants.

## Next Major Milestone
Yuplan Kommun 1.0 - Ready for Pilot.

Order:
1. Close and freeze the remaining Builder/Menu/Offshore seam.
2. Ground Truth / Planera 2.0 Architecture Lock - COMPLETE.
3. Portal Foundation / Avdelningsportal canonical-path consolidation.
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
After scope prevention, legacy-scope containment, and live parity are accepted, freeze broad Builder/Menu MVP work. Only pilot-blocking defects may reopen the seam before Kommun 1.0 Ready for Pilot.
