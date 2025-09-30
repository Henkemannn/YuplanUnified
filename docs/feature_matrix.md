# Feature Matrix: Legacy (Kommun & Offshore) vs Unified

Status legend: ✅ done  🔄 in-progress  🕓 planned  ⛔ not-started  🚧 partial

| Domain / Area | Legacy Kommun | Legacy Offshore | Unified Core Models | Unified API/UI Status | Gap / Action |
|---------------|---------------|-----------------|--------------------|-----------------------|--------------|
| Tenancy / Rigg | Single DB + implicit | Rigs (multi) | tenants, units | Basic creation (bootstrap only) | Add tenant create via superuser UI |
| Units / Avdelningar | avdelningar table | users.rig_id context | units | Read via Kommun adapter | Write (create/edit) + attendance editing |
| Dietary Types / Kosttyper | kosttyper + avdelning_kosttyp | minimal / none | dietary_types, unit_diet_assignments | Read-only mapping adapter | CRUD endpoints + UI form persistence |
| Weekly Menu Structure | veckomeny alt1/alt2/dessert/kväll | menu_dish_map categories (soppa/fisk/kött/extra) | menus, menu_variants, dishes | Import populates variants | UI editing per day/meal/variant missing |
| Menu Import (DOCX/XLSX) | DOCX form | Excel/CSV | Import pipeline & service | Endpoint + kommun import page | Dry-run preview & diff, error UI |
| Attendance / Boende antal | boende_antal + registreringar | service metrics partly | attendance | API exists | UI integration / editing per unit/day |
| Feature Flags | N/A | N/A | tenant_feature_flags | Model only | Toggle endpoint + UI |
| Recipes | Minimal / text in menus | Full recipe CRUD | recipes | Model only | CRUD service + adapter UI |
| Turnus / Rotation | N/A | rotation / schedule | shift_templates, shift_slots | Models only | Migration plan & mapping code |
| Service Metrics / Waste | N/A | service_metrics + waste | service_metrics | Model only | Import/aggregation endpoints |
| Messaging | N/A | messages | messages | Model only | UI + send/filter endpoints |
| Tasks / Prep & Freezer | N/A | prep tasks in UI | tasks | Model only | Endpoints + adapter lists |
| Overrides / Local Changes | local alt? (manual) | per day form edits | menu_overrides | Not exposed | Apply override logic in week view |
| Auth Roles | admin, avdelning login | admin, user, superuser | user.role (superuser/admin/cook/unit_portal) | Basic auth endpoints | Password reset, user mgmt UI |
| Superuser Panel | Basic adminpanel | Full rigg panel | tenants -> rigs mapping | Offshore panel adapted | Create tenant via panel |
| Report Export | Rapport (Excel) | None/metrics pages | attendance/service_metrics | Not exposed | Build aggregated endpoints + export |
| Menu Builder (Fragments) | N/A | N/A | (planned fragments) | Not started | Schema + extraction logic |
| Allergen / Tags | basic? (not structured) | some inline badges | dish.category only | Not structured | dish_tags table + importer mapping |

## Immediate Action Items
1. Tenant creation via superuser panel (model or service + UI form).
2. Kosttyp CRUD + Unit assignment update (Kommun adapter POST support).
3. Feature toggle endpoint + minimal UI (checkbox list).
4. Menu variant editing UI (Kommun: per dag/alt; Offshore: category mapping view).
5. Import dry-run & diff (no DB writes).
6. Recipe CRUD service + adapter to offshore recipe_list/recipe_detail templates.

## Mapping Strategy
- Kommun alt1/alt2/dessert/kväll -> variant_types: alt1, alt2, dessert, kvall (normalized lowercase).
- Offshore categories (soppa,fisk,kött,extra) -> dish.category; presented as variant grouping per meal.
- Unify day tokens: Mån,Tis,Ons,Tors,Fre,Lör,Sön.

## Risks / Considerations
- Dual semantics (alt vs category) need a canonical abstraction for UI editing; propose: meal -> slots (ordered), each slot references variant_type or category label.
- Legacy direct-SQL side effects avoided by adapter—but ensure transactional integrity when we add POST.
- Turnus logic large: isolate into service layer before UI plug.

## Proposed Milestones
M1: Import + Read-only admin views (DONE)
M2: CRUD: Units, Dietary Types, Feature Toggles, Tenants (IN PROGRESS soon)
M3: Menu editing UI + variant/category mapping
M4: Recipe integration + basic service metrics ingestion
M5: Turnus migration plan + initial shift generation
M6: Menu Builder fragments + override logic

