# Offshore 2.0 - Current State And First Slice

## Executive Summary
Offshore 2.0 should become a business adapter on top of Builder and Planera 2.0, not a parallel menu system. The current codebase already has a real production engine in `core/planera_v2`, a real Builder menu/composition context in `core/builder_menu_context_flow.py`, and legacy Offshore-only remnants in `modules/offshore/views.py`, `core/legacy_offshore_ui.py`, plus old architecture docs. The product decision for the next code ticket is the Offshore foundation/app shell, not a read-only projection slice.

## 1. Current Code Inventory

### Active Planera 2.0 engine
- File: `core/planera_v2/domain.py`
  - Classes/functions: `Deviation`, `UnitInput`, `PlanRequest`, `Totals`, `UnitBreakdown`, `PlanResult`
  - Purpose: normalized engine input/output model.
  - Data in: baseline, units, deviations, context.
  - Data out: deterministic production totals and breakdowns.
  - Source: pure domain dataclasses.
  - Test coverage: `tests/core/test_planera_v2_engine.py`, `tests/core/test_planera_v2_service.py`, `tests/core/test_planera_v2_comparison.py`, `tests/core/test_planera_v2_formatter.py`, `tests/core/test_planera_v2_kitchen_formatter.py`, `tests/core/test_planera_v2_dev_runner.py`.
  - Status: active.

- File: `core/planera_v2/engine.py`
  - Function: `compute_plan`
  - Purpose: pure calculation engine, no DB/UI.
  - Data in: `PlanRequest`.
  - Data out: `PlanResult`.
  - Source: engine only.
  - Test coverage: direct engine tests plus service/comparison tests.
  - Status: active.

- File: `core/planera_v2/service.py`
  - Functions: `build_plan_request_from_adapter_payload`, `run_plan`, `run_plan_from_payload`
  - Purpose: application wrapper around the engine.
  - Data in: generic adapter payload.
  - Data out: `PlanRequest` or `PlanResult`.
  - Source: adapter payload.
  - Test coverage: `tests/core/test_planera_v2_service.py`.
  - Status: active.

- File: `core/planera_v2/adapters/kommun_adapter.py`
  - Function: `build_payload_from_kommun_input`
  - Purpose: converts kommun-style input into normalized Planera payload.
  - Data in: units, baseline, deviations, context.
  - Data out: canonical payload for the engine.
  - Source: kommun adapter input.
  - Test coverage: `tests/core/test_planera_v2_kommun_adapter.py`.
  - Status: active.

- File: `core/planera_v2/adapters/kommun_from_weekview.py`
  - Function: `build_plan_request_from_weekview_day`
  - Purpose: turns current weekview/department data into a Planera request.
  - Data in: `PlaneraService.compute_day(...)` payload.
  - Data out: `PlanRequest` with baseline, units, deviations, context.
  - Source: current weekview/department data.
  - Test coverage: `tests/core/test_planera_v2_kommun_from_weekview.py`.
  - Status: active.

- File: `core/planera_v2/adapters/menu_composition_adapter.py`
  - Functions: `build_menu_composition_payload`, `build_menu_composition_grouped_payload`, `build_menu_composition_production_shape_payload`
  - Purpose: maps Builder menu/composition rows into structured menu-context payloads and a production-shaped view.
  - Data in: menu + menu rows + composition repository.
  - Data out: grouped menu-composition payloads, readiness summary, and production-shape blocks.
  - Source: Builder menu context flow.
  - Test coverage: `tests/core/test_planera_v2_menu_composition_adapter.py`.
  - Status: active.

- File: `core/planera_v2/comparison.py`
  - Functions: `compare_current_planera_vs_v2_day`, `build_day_comparison_report`
  - Purpose: compare current Planera output against v2 dev-run output.
  - Data in: current day payload and v2 dev-run request/result.
  - Data out: comparison object and text report.
  - Source: current Planera service + dev runner.
  - Test coverage: `tests/core/test_planera_v2_comparison.py`.
  - Status: active.

- File: `core/planera_v2/dev_runner.py`
  - Functions: `run_planera_v2_from_current_day`, `format_dev_run_report`
  - Purpose: debug/dev harness for the v2 engine.
  - Data in: weekview-derived request.
  - Data out: formatted debug output and engine result.
  - Source: adapter + engine.
  - Test coverage: `tests/core/test_planera_v2_dev_runner.py`.
  - Status: active.

- File: `core/planera_v2/formatter.py`
  - Functions: `format_plan_result`, `format_plan_result_clean`, `format_plan_result_kitchen_view`
  - Purpose: readable production output formats.
  - Data in: `PlanResult`.
  - Data out: human-readable strings.
  - Source: engine result.
  - Test coverage: `tests/core/test_planera_v2_formatter.py`, `tests/core/test_planera_v2_kitchen_formatter.py`.
  - Status: active.

### Current Planera 1.0/legacy service and API
- File: `core/planera_service.py`
  - Class: `PlaneraService`
  - Purpose: current aggregation service for day/week planning and registration status.
  - Data in: tenant/site/date/week and existing weekview-style department payloads.
  - Data out: day/week summaries, totals, and registration state.
  - Source: legacy Weekview data.
  - Test coverage: exercised indirectly by Planera v2 adapters and current planera tests.
  - Status: active legacy bridge.

- File: `core/planera_api.py`
  - Routes: `/api/planera/day`, `/api/planera/week`, `/api/planera/week/csv`, `/kitchen/planering/normal_exclusions/toggle`
  - Purpose: API surface for current Planera views and the normal-exclusion toggle.
  - Data in: tenant/session, site, department, date/week query params, request JSON.
  - Data out: JSON payloads or CSV.
  - Source: `PlaneraService` and current weekview data.
  - Test coverage: planera endpoint tests under `tests/planera/`.
  - Status: active.

- File: `core/ui_blueprint.py`
  - Routes: `/ui/planera/day`, `/ui/planera/week` and related weekview routes.
  - Purpose: UI wrapper around current Planera endpoints.
  - Data in/out: site-scoped UI payloads.
  - Source: `PlaneraService` and current weekview data.
  - Test coverage: `tests/planera/*`, portal/weekview tests.
  - Status: active.

### Builder menu/composition stack
- File: `core/menu/menu_domain.py`
  - Classes: `Menu`, `MenuDetail`
  - Purpose: in-memory Builder menu domain.
  - Data in/out: menu identity, status, resolved/unresolved rows.
  - Source: Builder context flow.
  - Test coverage: Builder/menu context tests.
  - Status: active library model.

- File: `core/menu/menu_service.py`
  - Class: `MenuService`
  - Purpose: in-memory menu service for creating/updating menus and rows.
  - Data in/out: menu rows, import rows, declaration readiness, cost overview.
  - Source: menu domain + composition repository.
  - Test coverage: `tests/core/test_builder_menu_context_flow.py`, `tests/core/test_commun_builder_import.py`, `tests/core/test_commun_builder_projection.py`.
  - Status: active library/service.

- File: `core/menu/menu_import_service.py`
  - Function: `import_menu_rows`
  - Purpose: text import into resolved/unresolved menu rows.
  - Data in: imported raw text rows.
  - Data out: import summary with resolved/unresolved counts.
  - Source: composition resolution.
  - Test coverage: `tests/core/test_commun_builder_import.py`.
  - Status: active.

- File: `core/menu/composition_resolution.py`
  - Functions: `normalize_menu_import_text`, `resolve_composition_reference`, `create_composition_alias`
  - Purpose: deterministic alias/canonical-name resolution for imported menu text.
  - Data in: raw import text, composition repository, alias repository.
  - Data out: resolved composition or unresolved text.
  - Source: Builder canonical data and aliases.
  - Test coverage: `tests/core/test_commun_builder_import.py`.
  - Status: active.

- File: `core/builder_menu_context_flow.py`
  - Class: `BuilderMenuContextFlow`
  - Purpose: orchestrates Builder menus and exposes menu-context payloads.
  - Data in: Builder menu service, composition repo, alias repo, recipe repo, ingredient repo, library flow.
  - Data out: menu CRUD, row CRUD, grouped rows, production-shaped payloads, readiness, cost overview.
  - Source: Builder library + menu context.
  - Test coverage: `tests/core/test_builder_menu_context_flow.py`, `tests/core/test_builder_sqlite_persistence.py`, `tests/core/test_commun_builder_import.py`, `tests/core/test_commun_builder_projection.py`.
  - Status: active.

- File: `core/builder_menu_context_api.py`
  - Blueprint: `/api/builder/menus`
  - Purpose: API for Builder menu context CRUD and adapters.
  - Data in: JSON payloads for menu/create/rows/adapter queries.
  - Data out: menu, rows, readiness, cost, grouped and production-shape payloads.
  - Source: `BuilderMenuContextFlow`.
  - Test coverage: `tests/api/test_builder_menu_context_api.py`.
  - Status: active.

- File: `core/commun_builder_import.py`
  - Function: `import_menu_result_to_builder_canonical`
  - Purpose: canonical import from legacy/import source into Builder menus and linkage.
  - Data in: imported weeks and rows.
  - Data out: Builder menus, rows, links, outcomes.
  - Source: Builder flow + linkage service.
  - Test coverage: `tests/core/test_commun_builder_import.py`.
  - Status: active.

- File: `core/commun_builder_linkage.py`
  - Class: `CommunBuilderMenuLinkService`
  - Purpose: durable link between legacy menu/week and Builder menu/version.
  - Data in: tenant/site/year/week, Builder menu ID/version, legacy menu ID.
  - Data out: link rows in `commun_builder_menu_links`.
  - Source: Builder menu context flow and site ownership checks.
  - Test coverage: `tests/core/test_commun_builder_linkage.py`.
  - Status: active.

- File: `core/commun_builder_projection.py`
  - Class: `CommunBuilderMenuProjectionReader`
  - Purpose: projection from pinned Builder menu back into legacy/menu-context shape.
  - Data in: builder link, publication pin, Builder menu context flow.
  - Data out: projection outcome and comparison against legacy.
  - Source: Builder link + publication pin + menu context flow.
  - Test coverage: `tests/core/test_commun_builder_projection.py`.
  - Status: active.

- File: `core/commun_builder_publication.py`
  - Class: `CommunBuilderPublicationService`
  - Purpose: manages publication pins for Builder-backed menus.
  - Data in: tenant/site/year/week, legacy menu ID, Builder link, projection verification.
  - Data out: publication pin rows in `commun_builder_publication_pins`.
  - Source: Builder link + projection verification.
  - Test coverage: `tests/core/test_commun_builder_publication.py`.
  - Status: active.

### Legacy Offshore / Rigplan remnants
- File: `modules/offshore/views.py`
  - Blueprint: `/offshore/ping`
  - Purpose: minimal leftover module presence only.
  - Data in/out: static ping response.
  - Source: module stub.
  - Test coverage: none found.
  - Status: legacy / unused.

- Documentation only:
  - `docs/legacy_inventory_offshore.md`
  - `docs/legacy_functional_overview.md`
  - `docs/turnus_migration_plan.md`
  - `docs/modules.md`
  - `docs/feature_matrix.md`
  - `docs/feature_parity_matrix.md`
  - `docs/planera2/*`
  - Status: reference only unless explicitly contradicted by active code.

### Generic scheduling / turnus
- File: `core/turnus_service.py`
  - Class: `TurnusService`
  - Purpose: simple generic shift template and slot CRUD/query service.
  - Data in: templates, shifts, date range, role, unit IDs.
  - Data out: template lists, inserted/skipped counts, slot lists.
  - Source: SQLite/DB tables `shift_templates`, `shift_slots`.
  - Test coverage: `tests/test_turnus_endpoints.py`.
  - Status: active but minimal.

- File: `core/turnus_api.py`
  - Routes: `/turnus/templates`, `/turnus/import`, `/turnus/slots`
  - Purpose: thin API for turnus CRUD/import/query.
  - Data in/out: JSON and query params.
  - Source: `TurnusService`.
  - Test coverage: `tests/test_turnus_endpoints.py`.
  - Status: active but minimal.

### Related production helpers
- File: `core/portion_recommendation_service.py`, `core/portion_service.py`, `core/production_lists_repo.py`, `core/prep_notes_repo.py`, `core/tasks_service.py`
  - Purpose: adjacent production/prep helpers.
  - Status: active utility layer, but not a Planera 2.0 engine.

## 2. Current Planera 2.0 Pipeline
The actual pipeline that exists today is:

`Builder/kommun/weekview adapter` -> `PlaneraRequest` -> `compute_plan` -> `PlanResult` -> formatter/comparison/dev-run output.

For current legacy data the effective path is:
- `core/planera_service.PlaneraService.compute_day/compute_week`
- `core/planera_v2.adapters.kommun_from_weekview.build_plan_request_from_weekview_day`
- `core/planera_v2.engine.compute_plan`
- `core/planera_v2.formatter` / `core/planera_v2.dev_runner`
- `core/planera_v2.comparison.compare_current_planera_vs_v2_day`

For Builder menus the effective path is:
- `BuilderMenuContextFlow`
- `build_menu_composition_payload` / `build_menu_composition_grouped_payload` / `build_menu_composition_production_shape_payload`
- current tests show this is an active and stable adapter seam for menu context, but not yet a full Offshore production planner.

The engine is therefore:
- fully functioning as a generic calculation core
- blocked only by missing offshore-specific business adapter and menu assignment layer
- not blocked by the engine itself

## 3. Legacy Offshore / Rigplan Classification

### REUSE
- `core/turnus_service.py` / `core/turnus_api.py` for generic date-range shift primitives.
- `core/menu/composition_resolution.py` for deterministic import resolution.
- `core/menu/menu_service.py` and `core/menu/menu_import_service.py` for Builder-backed menu rows.
- `core/builder_menu_context_flow.py` and `core/planera_v2/adapters/menu_composition_adapter.py` for menu-to-production-shape normalization.

### ADAPT
- `core/planera_service.py` for producing the normalized current-day/week input from site/dept data.
- `core/planera_v2/adapters/kommun_from_weekview.py` for turning domain rows into production input.
- `core/commun_builder_import.py`, `core/commun_builder_linkage.py`, `core/commun_builder_projection.py`, `core/commun_builder_publication.py` as the Builder canonical data path that Offshore should consume indirectly.

### REFERENCE ONLY
- `docs/legacy_inventory_offshore.md`
- `docs/legacy_functional_overview.md`
- `docs/turnus_migration_plan.md`
- `modules/offshore/views.py` as a stub
- old wording around Rigplan-specific CSVs, exports, and menus in docs

### RETIRE LATER
- Any legacy Offshore route/model ideas that duplicate Builder or Planera responsibilities.
- Direct text-based menu ownership for Offshore.

### DO NOT USE
- Reintroducing a separate offshore menu database.
- Reintroducing name-based identity as authoritative.
- Building a second parallel production engine.

## 4. Architecture Ownership

### Builder owns
- Components and compositions.
- Canonical identity and aliases.
- Menu row resolution / unresolved state.
- Builder menu context and declaration readiness.
- Builder publication linkage and publication pins.

### Planera 2.0 owns
- Generic production calculation.
- Baseline, deviations, totals, per-unit breakdowns.
- Deterministic normalization of engine input/output.
- Future prep/freezer/purchasing math as calculations, not UI.

### Offshore owns
- Rig/site assignment.
- Rotation and calendar mapping.
- Day/night week interpretation.
- Local planning status for Offshore use cases.
- Portions at the business level.
- Handover, reminders, prep/frys, and portal-facing operational outputs.

### Conflicts / unclear ownership
- `menu_option_by_unit` currently sits in Planera v2 context as adapter metadata, but business meaning likely belongs to Offshore or another adapter layer.
- `turnus` is currently generic; Offshore-specific rotation semantics should be an adapter/template layer, not engine logic.
- `production_shape` currently exists as a Builder menu adapter; it is a good candidate to feed Offshore, but it is not yet an Offshore domain model.

## 5. Rotation Model
The first realistic rotation should be represented as a combination of:
- a generic schedule template for reusable turnus math
- an Offshore-specific assignment/read model for a rig and calendar week
- date-range/service events for handover and production windows

Recommended representation for the first slice:
- schedule template: generic enough for 2/4 and 14/14-style cycles
- instance: rigidly ties a Builder menu version to a rig/site/week and rotation week number
- output: read-only production projection with lunch/dinner and unresolved rows visible

Do not encode the user’s exact shift pattern directly in the generic engine.

## 6. Builder Integration
The current Builder-to-production path that can be reused is:

`Builder Menu` -> `publicated/godkänd menu/version` -> `BuilderMenuContextFlow` -> `production_shape payload` -> `Planera 2.0 input` -> production projection.

Current contracts that matter:
- tenant: already enforced by site/tenant validation in Builder linkage and app feature flags.
- site/rig: currently `site_id`; Offshore should probably map its rig/site identity here.
- menu ID: Builder `menu_id`.
- menu version: Builder menu `version`, and later publication pin version.
- calendar year/week: stored in linkage/publication and turnus queries.
- date/day/meal slot: retained in menu rows and production adapter context.
- `composition_id`: authoritative resolved identity.
- `unresolved_text`: preserved and visible; should not be silently collapsed.
- portions: belongs to Planera/production layer, not Builder identity.
- status: `draft`/`published` belong to menu/publication semantics; Offshore should not own Builder publication state.

Critical rule: name matching must never be permanent identity.

## 7. First Implementation Slice
The current technical inventory points to the shell and context layer as the first coded step, because Offshore still does not exist as a real module.

The next ticket should build:
1. a new Offshore app shell and `/offshore` entry point
2. installation and tenant/site context handling
3. a professional empty dashboard and navigation scaffold
4. a settings skeleton that can later host menu cycle and period setup

What it should not do yet:
- implement the period model
- implement menu cycle assignment
- implement Builder projection logic
- write prep or freezer data
- write handover data
- add new production tables

## 8. Persistence Assessment
These future concepts are likely needed, but not all in the first slice:

- `OffshoreRotationTemplate`
  - Needed later for reusable cycles.
  - Can be derivable/read-model first.
  - Eventually persistent.
  - Likely Offshore-owned.

- `OffshoreRotationInstance`
  - Needed later for one rig/week assignment.
  - Could be read-only initially if derived from existing menu publication + rotation template.
  - Eventually persistent.
  - Offshore-owned.

- `OffshoreMenuAssignment`
  - Needed earlier if you want a durable link from Builder menu/version to Offshore week.
  - Persistent once the first nontrivial slice goes beyond read-only.
  - Boundary between Builder data and Offshore business use.

- `OffshoreServiceEvent`
  - Needed for handover windows and special service moments.
  - Can remain derivable until real scheduling output exists.
  - Offshore-owned.

- `OffshoreProductionPlan`
  - Likely the first serious persistence candidate after the read-only slice.
  - Could be read model at first.
  - Offshore-owned, computed from Planera.

- `OffshorePrepTask`
  - Later, after production plan exists.
  - Probably persistent.
  - Offshore-owned, powered by Planera.

- `OffshoreFreezerPick`
  - Later still.
  - Persistent or derived depending on operations.
  - Offshore-owned.

- `OffshoreHandover`
  - Later; can begin as derived output.
  - Offshore-owned.

## 9. Security
Current reusable security patterns:
- tenant and site scoping in app-level feature flags and menu/publication services
- role-based route guards in the API and UI blueprints
- site ownership validation in Builder linkage
- read-only adapters that never write on behalf of consumers

Requirements for Offshore:
- tenant isolation must stay strict
- rig/site isolation must be explicit
- menu/version leakage across sites must be blocked
- role boundaries should distinguish admin/cook/unit portal if Offshore-facing UI appears later
- read-only preview should not expose Builder internal IDs unless explicitly needed in backend-only telemetry

## 10. Proposed Ticket Sequence

### Ticket 2 - Offshore contracts and rotation template
- Goal: define a minimal Offshore assignment/read contract.
- Layers: docs + read model + maybe characterization tests.
- Feature flag: `offshore.v2.enabled` or similar, default off.
- Tests: contract and isolation tests.
- Rollback: disable flag.
- Dependencies: current Builder publication/linkage.

### Ticket 3 - Builder menu assignment
- Goal: durable assignment from Builder publication to Offshore week.
- Layers: adapter/service only.
- Feature flag: `offshore.builder_menu_assignment_v0`.
- Tests: link selection and mismatch cases.
- Rollback: flag off, preserve legacy path.

### Ticket 4 - Read-only Planera projection
- Goal: read-only weekly production projection for lunch/dinner.
- Layers: adapter + Planera v2 input/output.
- Feature flag: `offshore.planera_projection_v0`.
- Tests: deep-equal legacy fallback, unresolved visibility.
- Rollback: flag off.

### Ticket 5 - Production plan read model
- Goal: materialize or cache production output.
- Layers: read model only, no write automation.
- Feature flag: `offshore.production_plan_v0`.
- Tests: deterministic projection and tenant isolation.
- Rollback: delete/read-disable path.

### Ticket 6 - Prep and handover outputs
- Goal: derive prep tasks and handover from production plan.
- Layers: adapter + output formatting.
- Feature flag: `offshore.prep_handover_v0`.
- Tests: read-only derivation.
- Rollback: disable.

### Ticket 7 - Freezer pick and order reminder planning
- Goal: derive freezer and reminder outputs from the same normalized plan.
- Layers: read model and UI/API output only.
- Feature flag: `offshore.freezer_order_v0`.
- Tests: no writes, no duplicated logic.
- Rollback: disable.

## 11. Risks
- The current engine is healthy, but business semantics for Offshore are not yet formalized.
- `PlaneraService` still depends on current weekview data; Offshore should not copy that dependency forever.
- If Offshore gets its own adapter too early, it could become a second parallel menu system.
- Legacy docs still describe menu and rotation behavior that is not authoritative anymore.
- `menu_option_by_unit` and generic `turnus` can become ambiguous if they are not frozen as adapter-only concepts.

## 12. Rollback Strategy
- Keep Offshore work behind a separate flag.
- Prefer read-only adapters and read models first.
- Preserve Builder publication/linkage as the source of truth.
- Never couple new Offshore logic to legacy text menus as identity.
- If a slice misbehaves, disable the flag and keep the existing Planera/Builder flows untouched.

## 13. Definition of Done For Offshore v0
- Builder menu data can be assigned to a rig/site/week.
- A read-only weekly production projection can be generated.
- Lunch/dinner and unresolved rows are visible.
- No new menu system is created.
- No migrations are required for the first slice.
- The engine remains generic and testable.
- Offshore behavior is isolated behind flags and adapters.

## 14. Notes On What Exists Vs Vision
- Existing and active: Planera v2 engine/service/adapters, Builder menu context flow, Builder linkage/import/projection/publication, turnus service/API, current planera API/UI.
- Legacy or reference-only: Offshore legacy inventory docs and `modules/offshore/views.py` stub.
- Future vision only: full Offshore rotation engine, prep/freezer persistence, handover workflows, and crew portal integration.
