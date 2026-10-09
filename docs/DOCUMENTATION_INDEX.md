Status: ACTIVE INDEX
Last reviewed: 2026-10-09

# Yuplan Documentation Index

## Purpose

This is the navigation and governance index for Yuplan documentation. It answers:

- what documents exist;
- where they live;
- what they are for;
- which documents are canonical vs supporting/history;
- which documents are candidates for archive.

Repository snapshot at this review contains **133 Markdown documents** under `docs/` plus non-Markdown design/assets.

## Status vocabulary

- **CANONICAL** — Ground Truth. Current product/architecture authority.
- **ACTIVE REFERENCE** — useful current detailed architecture/spec/reference; does not override Ground Truth.
- **OPS REFERENCE** — deployment/release/observability/staging operating material.
- **HANDOFF** — point-in-time project state. Useful during transition, then historical.
- **FUTURE LAB** — deliberately non-current product exploration.
- **AUDIT / REVIEW** — evidence/audit material; useful but may age quickly.
- **REVIEW** — not yet classified strongly enough to archive.
- **SUPERSEDED POINTER** — should point readers to newer canonical direction.
- **ARCHIVE CANDIDATE** — historical/legacy/checklist/PR snapshot; retain for evidence but remove from normal navigation after link audit.

## Authority order

1. `docs/ground_truth/*`
2. current implementation + accepted checkpoint evidence
3. active module/reference docs
4. handoffs/audits
5. legacy/archive material

If a lower layer conflicts with Ground Truth, Ground Truth wins.

## Inventory


### CANONICAL

| Path | What it describes |
|---|---|
| `docs/ground_truth/BUILDER_MENU_LOCK.md` | Locked Builder/Menu ownership and canonical menu identity rules. |
| `docs/ground_truth/DECISION_LOG.md` | Chronological log of deliberate Ground Truth decisions and supersessions. |
| `docs/ground_truth/KOMMUN_1_0_MVP_LOCK.md` | Locked Kommun 1.1 MVP product/production contract and parity target. |
| `docs/ground_truth/KOMMUN_MENUIMPORT_EDITING_LOCK.md` | Locked Kommun menu-import/editing ownership and interaction rules. |
| `docs/ground_truth/OFFSHORE_1_0_MVP_LOCK.md` | Locked Offshore 1.0 MVP boundary and product target. |
| `docs/ground_truth/PLANERA_2_0_ARCHITECTURE_LOCK.md` | Locked Planera 2.0 engine/application architecture. |
| `docs/ground_truth/PLATFORM_ARCHITECTURE_LOCK.md` | Locked shared-platform architecture principles. |
| `docs/ground_truth/PORTALS_ARCHITECTURE_LOCK.md` | Locked Portal Foundation and domain-adapter boundaries. |
| `docs/ground_truth/README.md` | Index and rules for canonical Ground Truth. |
| `docs/ground_truth/USER_PROVISIONING_AND_AUTH_FLOW.md` | Locked user provisioning, scope binding, login, account lifecycle and auth-revocation direction. |
| `docs/ground_truth/YUPLAN_1_0_FINISHLINE.md` | Current Yuplan 1.0 finish-line state, closure rules and sequencing. |

### ACTIVE REFERENCE

| Path | What it describes |
|---|---|
| `docs/Platform/README.md` | Platform reference: README. |
| `docs/Platform/ai_data_truth_principles.md` | Principles for AI consuming canonical data without becoming a source of truth. |
| `docs/Platform/calendar_read_contract.md` | Read-only shared calendar/timeline contract; Offshore adapter implemented, other adapters future. |
| `docs/Platform/crew_portal_architecture.md` | Future/shared Crew Portal architecture direction. |
| `docs/Platform/department_portal_architecture.md` | Detailed Department Portal architecture supporting the portal Ground Truth. |
| `docs/Platform/menu_context_architecture.md` | Shared menu-context architecture and ownership boundaries. |
| `docs/Platform/recipe_knowledge_layer_architecture.md` | Recipe/knowledge-layer architecture, versioning, visibility and workflow integration. |
| `docs/Platform/yuplan_system_overview.md` | Platform-level system overview and module relationships. |
| `docs/adr/ADR_department_portal_composite_and_etags.md` | ADR for Department Portal composite payload/ETag behavior. |
| `docs/architecture/engine-ownership.md` | Ownership boundary between generic engine and application/domain layers. |
| `docs/builder/allergen_display_codes.md` | Allergen display-code conventions for Builder. |
| `docs/builder/builder_import_architecture.md` | Builder import architecture and resolution rules. |
| `docs/builder/custom_dietary_markers.md` | Custom dietary-marker conventions for Builder. |
| `docs/offshore2/README.md` | Offshore 2.0 reference: README. |
| `docs/offshore2/cook_operational_view.md` | Offshore cook-facing operational view specification. |
| `docs/offshore2/current_state_and_first_slice.md` | Offshore 2.0 current implementation state and recommended first slice. |
| `docs/offshore2/demo_smoke_setup.md` | Offshore demo/smoke environment setup. |
| `docs/offshore2/menu_context.md` | Offshore menu-context model and Builder publication mapping. |
| `docs/offshore2/periods_and_service_events.md` | Offshore periods/service-event model. |
| `docs/offshore2/prep_tasks.md` | Offshore prep-task model and workflow. |
| `docs/offshore2/product_blueprint.md` | Detailed Offshore 2.0 product blueprint, user journey and module surfaces. |
| `docs/offshore2/technical_model_notes.md` | Supporting Offshore technical model notes. |
| `docs/planera2/KOMMUN_STANDING_NEEDS_AND_PACKING.md` | Current detailed Kommun standing-needs and packing design reference. |
| `docs/planera2/PLANERA_KOMMUN_UX_MALBILD.md` | Kommun Planera UX target/reference. |
| `docs/planera2/PRODUCTION_NEEDS_V1.md` | Planned read-only raw-material/production-needs projection derived from menu, demand and recipes. |
| `docs/planera2/component_composition_architecture.md` | Component/composition architecture supporting Builder and Planera. |
| `docs/planera2/component_model_v1.md` | Component model v1 specification. |
| `docs/planera2/component_recipe_architecture.md` | Component-to-recipe architecture. |
| `docs/planera2/eventcase_domain_architecture.md` | Future EventCase/Hotel/Bankett domain architecture. |
| `docs/planera2/ingredient_purchasing_architecture.md` | Ingredient/purchasing architecture and future supplier layer. |
| `docs/planera2/menu_component_architecture.md` | Menu/component architecture reference. |
| `docs/planera2/menu_composition_integration.md` | Menu-to-composition integration reference. |
| `docs/planera2/planera2_ai.md` | Future AI-assistance boundaries and staged capabilities for Planera. |
| `docs/planera2/planera2_architecture.md` | Supporting Planera 2.0 architecture reference. |
| `docs/planera2/planera2_motor_flow.md` | Planera 2.0 engine flow reference. |
| `docs/planera2/planera2_vision.md` | Planera 2.0 product/architecture vision. |

### OPS REFERENCE

| Path | What it describes |
|---|---|
| `docs/OBSERVABILITY.md` | Documentation/reference for OBSERVABILITY. |
| `docs/OTEL_SETUP.md` | Documentation/reference for OTEL SETUP. |
| `docs/RELEASE_RUNBOOK.md` | Documentation/reference for RELEASE RUNBOOK. |
| `docs/STAGING_SECURITY.md` | Documentation/reference for STAGING SECURITY. |
| `docs/branch-protection.md` | Documentation/reference for branch protection. |
| `docs/deployment.md` | Documentation/reference for deployment. |
| `docs/staging-access.md` | Staging/operations reference: staging access. |
| `docs/staging_postgres_runbook.md` | Staging/operations reference: staging postgres runbook. |

### HANDOFF

| Path | What it describes |
|---|---|
| `docs/handoffs/KOMMUN_1_1_HANDOFF_2026-10-07.md` | Project handoff snapshot for Kommun 1.1 on 2026-10-07. |
| `docs/handoffs/KOMMUN_MENUIMPORT_STABILIZATION_2026-10-08.md` | Focused Menyimport stabilization handoff/evidence. |

### FUTURE LAB

| Path | What it describes |
|---|---|
| `docs/future_lab/YUPLAN_HOME.md` | Future Lab product concept for consumer weekly planning, recipes, shopping and retailer adapters. |

### AUDIT / REVIEW

| Path | What it describes |
|---|---|
| `docs/Platform/commun_ui_reference_audit.md` | Audit/reference of existing Kommun UI patterns and reuse candidates. |
| `docs/Platform/date_messages_reminders_portal_audit.md` | Audit of dates/messages/reminders/portal-ready capabilities and reuse candidates. |
| `docs/Platform/date_messages_reminders_portal_audit_appendix.md` | Appendix/evidence for the dates/messages/reminders audit. |

### REVIEW

| Path | What it describes |
|---|---|
| `docs/429-standardization.md` | Documentation/reference for 429 standardization. |
| `docs/CONSUMERS.md` | Documentation/reference for CONSUMERS. |
| `docs/DECISIONS_AUDIT.md` | Documentation/reference for DECISIONS AUDIT. |
| `docs/DECISIONS_LIMITS_AUDIT.md` | Documentation/reference for DECISIONS LIMITS AUDIT. |
| `docs/DECISIONS_PAGINATION.md` | Documentation/reference for DECISIONS PAGINATION. |
| `docs/DECISIONS_TOKEN_BUCKET.md` | Documentation/reference for DECISIONS TOKEN BUCKET. |
| `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md` | Operator/live acceptance checklist for Kommun 1.1. |
| `docs/NDA_TEMPLATE.md` | Documentation/reference for NDA TEMPLATE. |
| `docs/README.md` | Entry point for the documentation tree and documentation governance. |
| `docs/admin.md` | Admin reference/checklist: admin. |
| `docs/admin_authz_phase2_checklist.md` | Authentication/authorization reference: admin authz phase2 checklist. |
| `docs/admin_authz_phase3_checklist.md` | Authentication/authorization reference: admin authz phase3 checklist. |
| `docs/api_overview.md` | Documentation/reference for api overview. |
| `docs/architecture.md` | Documentation/reference for architecture. |
| `docs/auth_hardening.md` | Authentication/authorization reference: auth hardening. |
| `docs/auth_reset.md` | Authentication/authorization reference: auth reset. |
| `docs/brand/YUPLAN_BRAND_BASE_1_0.md` | Canonical current brand base/reference. |
| `docs/branding.md` | Documentation/reference for branding. |
| `docs/builder_ui_blueprint.md` | Documentation/reference for builder ui blueprint. |
| `docs/data_model.md` | Documentation/reference for data model. |
| `docs/department_portal_week_schema.md` | Documentation/reference for department portal week schema. |
| `docs/feature_matrix.md` | Documentation/reference for feature matrix. |
| `docs/kommun/ACTIVE_KOMMUN_RUNTIME_DISCOVERY_LOG_2026-08-27.md` | Historical runtime-discovery log for Kommun. |
| `docs/meal_labels.md` | Documentation/reference for meal labels. |
| `docs/menu_component_design.md` | Documentation/reference for menu component design. |
| `docs/menu_import.md` | Documentation/reference for menu import. |
| `docs/migration_plan.md` | Documentation/reference for migration plan. |
| `docs/modules.md` | Documentation/reference for modules. |
| `docs/optimistic-concurrency.md` | Documentation/reference for optimistic concurrency. |
| `docs/pilot_demo_guide.md` | Documentation/reference for pilot demo guide. |
| `docs/planera_day_unified.md` | Documentation/reference for planera day unified. |
| `docs/planera_module_functional_spec.md` | Documentation/reference for planera module functional spec. |
| `docs/portal_department_week.md` | Documentation/reference for portal department week. |
| `docs/problems.md` | Documentation/reference for problems. |
| `docs/report_current_behaviour.md` | Reporting reference/specification: report current behaviour. |
| `docs/report_week.md` | Reporting reference/specification: report week. |
| `docs/report_weekly_export_excel.md` | Reporting reference/specification: report weekly export excel. |
| `docs/report_weekly_export_pdf.md` | Reporting reference/specification: report weekly export pdf. |
| `docs/service_metrics_plan.md` | Documentation/reference for service metrics plan. |
| `docs/session-logs/README.md` | Documentation/reference for README. |
| `docs/staging_demo_kommun_core.md` | Staging/operations reference: staging demo kommun core. |
| `docs/turnus_migration_plan.md` | Documentation/reference for turnus migration plan. |
| `docs/unified_mapping.md` | Documentation/reference for unified mapping. |
| `docs/weekview.md` | Weekview reference/specification: weekview. |
| `docs/weekview_api_schema.md` | Weekview reference/specification: weekview api schema. |
| `docs/weekview_overview_design.md` | Weekview reference/specification: weekview overview design. |
| `docs/weekview_planning_issue.md` | Weekview reference/specification: weekview planning issue. |
| `docs/weekview_report_phase2e.md` | Reporting reference/specification: weekview report phase2e. |
| `docs/weekview_unified_proposal.md` | Weekview reference/specification: weekview unified proposal. |

### SUPERSEDED POINTER

| Path | What it describes |
|---|---|
| `docs/roadmap.md` | Older/current compact roadmap snapshot; superseded by the canonical product build order once that Ground Truth file is adopted. |

### ARCHIVE CANDIDATE

| Path | What it describes |
|---|---|
| `docs/GA_CHECKLIST_ISSUE.md` | Documentation/reference for GA CHECKLIST ISSUE. |
| `docs/GA_CHECKLIST_ISSUE_CONDENSED.md` | Documentation/reference for GA CHECKLIST ISSUE CONDENSED. |
| `docs/PR_POCKET5.md` | Documentation/reference for PR POCKET5. |
| `docs/RELEASE_BODY_v1.0.0.md` | Documentation/reference for RELEASE BODY v1.0.0. |
| `docs/ROADMAP_v1.1_ISSUE.md` | Documentation/reference for ROADMAP v1.1 ISSUE. |
| `docs/feature_parity_matrix.md` | Historical/transition parity reference: feature parity matrix. |
| `docs/legacy_functional_overview.md` | Legacy/historical reference: legacy functional overview. |
| `docs/legacy_inventory_kommun.md` | Legacy/historical reference: legacy inventory kommun. |
| `docs/legacy_inventory_offshore.md` | Legacy/historical reference: legacy inventory offshore. |
| `docs/legacy_rbac_ff.md` | Legacy/historical reference: legacy rbac ff. |
| `docs/legacy_routes_admin.md` | Legacy/historical reference: legacy routes admin. |
| `docs/legacy_routes_report.md` | Legacy/historical reference: legacy routes report. |
| `docs/legacy_routes_weekview.md` | Legacy/historical reference: legacy routes weekview. |
| `docs/phase_e_acceptance.md` | Documentation/reference for phase e acceptance. |
| `docs/planera_legacy_parity.md` | Legacy/historical reference: planera legacy parity. |
| `docs/portal_legacy_parity.md` | Legacy/historical reference: portal legacy parity. |
| `docs/pr/weekview_spec_pr.md` | Weekview reference/specification: weekview spec pr. |
| `docs/registrering_legacy_parity.md` | Legacy/historical reference: registrering legacy parity. |
| `docs/staging-smoke_2025-11-11.md` | Staging/operations reference: staging smoke 2025 11 11. |
| `docs/v1.0-beta-checklist.md` | Documentation/reference for v1.0 beta checklist. |
| `docs/weekview_legacy_analysis.md` | Legacy/historical reference: weekview legacy analysis. |
| `docs/weekview_report_legacy_parity.md` | Legacy/historical reference: weekview report legacy parity. |

## Recommended archive pass

Do **not** move files merely because they are old. First check inbound links/references.

Recommended archive buckets after link audit:

- `docs/archive/legacy/` — legacy routes, legacy inventories, parity snapshots.
- `docs/archive/audits/` — completed audits whose decisions have been promoted to Ground Truth.
- `docs/archive/handoffs/` — superseded handoffs after a newer handoff exists.
- `docs/archive/releases/` — old issue bodies, beta/release checklists and dated staging smoke evidence.
- `docs/archive/experiments/` — retired proposals/mockup documentation that is no longer an active product reference.

Archive means **historical evidence, not deletion**.

## First cleanup candidates

High-confidence candidates for archive review:

- `docs/legacy_*`
- `docs/*_legacy_parity.md`
- `docs/weekview_legacy_analysis.md`
- `docs/pr/*`
- `docs/PR_POCKET5.md`
- `docs/GA_CHECKLIST_ISSUE*.md`
- `docs/ROADMAP_v1.1_ISSUE.md`
- `docs/RELEASE_BODY_v1.0.0.md`
- `docs/staging-smoke_2025-11-11.md`
- `docs/phase_e_acceptance.md`
- `docs/v1.0-beta-checklist.md`

Likely supersession-review candidates:

- old auth/admin phase checklists now that `USER_PROVISIONING_AND_AUTH_FLOW.md` exists;
- old root architecture/data-model docs where newer Ground Truth or module architecture exists;
- old Weekview proposal/issue docs after accepted Weekview Ground Truth is fully captured;
- old menu import docs where `KOMMUN_MENUIMPORT_EDITING_LOCK.md` is authoritative.

## Governance rule

When a decision becomes durable:
1. promote the product/architecture rule into Ground Truth;
2. log the decision in `DECISION_LOG.md`;
3. demote point-in-time evidence to reference/archive status;
4. avoid creating another competing roadmap/spec for the same question.

The goal is fewer authoritative documents, not fewer historical records.
