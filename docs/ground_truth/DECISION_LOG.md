Status: LOCKED
Last reviewed: 2026-08-27

# Decision Log

## 2026-08-22
- Builder confirmed as canonical Knowledge Source of Truth.
- Planera 2.0 confirmed as generic Production Layer.
- Published Menu is immutable baseline.
- Effective Business Context sits between publication and production.
- Compatibility / Requirements becomes explicit application layer before Planera Core.
- Kommun selected as first full Planera 2.0 production integration.
- Planera 2.0 will enter Kommun through shadow and parity before cutover.
- Portal work will reuse and consolidate existing implementations instead of starting from zero.
- Main Yuplan 1.0 finishline prioritizes Kommun Ready for Pilot after the current Menu/Offshore seam closes.

## 2026-08-24
- Planning Slice confirmed as a non-canonical orchestration concept, not new source-of-truth persistence.
- Production Requirement must preserve traceable references to originating service, menu, Dish, and business context without Planera owning those objects.
- External menu-facing surfaces use effective_menu_name.
- Private Cook Work Menu or COW state is not portal or publication truth unless deliberately promoted or published.
- Planera 2.0 Architecture Lock marked complete; next launch path remains close Menu/Offshore seam -> Portal/Kommun integration -> Kommun Ready for Pilot.

## 2026-08-26
- Shared Builder runtime is the canonical direction; embedded Hosts remain thin.
- Legacy Builder scope inconsistency identified: old unscoped objects may be globally readable while newer objects are tenant scoped.
- This legacy condition must not drive cross-tenant visibility workarounds.
- Scope-aware canonical writes must not silently create unscoped Components/Compositions.
- organisation scope is tenant-local.
- private Cook/COW state is user isolated.
- legacy backfill must be provenance driven; no tenant guessing.
- missing-scope read compatibility is temporary.

## 2026-08-27
- Builder finishline narrowed to prevention -> legacy containment/repair -> deny-by-default/parity -> freeze.
- Offshore demo/provisioning actor context must come from a real principal in the same tenant; fabricated or cross-tenant principals are forbidden.
- Main launch path after Builder freeze remains Kommun 1.0 Ready for Pilot.
- Main Offshore development resumes after Kommun pilot-ready.
- Offshore 1.0 MVP is locked around Provisioning, Cook Operations and Crew Experience.
- External-service policy locked: integrate first; build own where Yuplan creates unique value.
- Live Builder/Host/Offshore Work Menu acceptance completed: existing canonical Dish selection, reload persistence, create Dish -> Component -> Work Menu, canonical edit refresh, and reset to published baseline all passed manual E2E verification.
- The shared Builder/Menu/Offshore seam is accepted and broad Builder/Menu MVP work is frozen. Only a concrete pilot-blocking regression or deliberate Ground Truth change may reopen it before Kommun 1.0 Ready for Pilot.
- Legacy unscoped read compatibility remains technical debt and does not define fresh-tenant architecture or justify reopening broad Builder product scope.
- Active launch work moves to Portal Foundation / Avdelningsportal canonical-path consolidation for Kommun 1.0.
