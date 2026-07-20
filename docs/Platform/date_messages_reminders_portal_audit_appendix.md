# Audit Appendix: File and Contract References

This appendix lists the main files and contracts referenced by the platform audit.

## Commun / Core

- [core/models.py](../../core/models.py)
  - `Message`
  - `Note`
  - `CommunBuilderMenuLink`
  - `CommunBuilderPublicationPin`
- [core/announcements_repo.py](../../core/announcements_repo.py)
- [core/notes_api.py](../../core/notes_api.py)
- [core/prep_notes_repo.py](../../core/prep_notes_repo.py)
- [core/remember_to_order_repo.py](../../core/remember_to_order_repo.py)
- [core/ui_blueprint.py](../../core/ui_blueprint.py)
- [core/menu_choice_api.py](../../core/menu_choice_api.py)
- [core/menu_choice_status.py](../../core/menu_choice_status.py)
- [core/weekview_vm.py](../../core/weekview_vm.py)
- [core/weekview/repo.py](../../core/weekview/repo.py)
- [core/commun_builder_publication.py](../../core/commun_builder_publication.py)
- [core/commun_builder_projection.py](../../core/commun_builder_projection.py)
- [core/builder_menu_context_flow.py](../../core/builder_menu_context_flow.py)
- [core/builder_menu_context_api.py](../../core/builder_menu_context_api.py)

## Offshore

- [modules/offshore2/models.py](../../modules/offshore2/models.py)
- [modules/offshore2/menu_context.py](../../modules/offshore2/menu_context.py)
- [modules/offshore2/periods.py](../../modules/offshore2/periods.py)
- [modules/offshore2/routes.py](../../modules/offshore2/routes.py)
- [modules/offshore2/permissions.py](../../modules/offshore2/permissions.py)
- [templates/offshore2/dashboard.html](../../templates/offshore2/dashboard.html)
- [templates/offshore2/periods.html](../../templates/offshore2/periods.html)
- [migrations/versions/0027_add_offshore_v2_periods.py](../../migrations/versions/0027_add_offshore_v2_periods.py)
- [migrations/versions/0028_add_offshore_v2_menu_context.py](../../migrations/versions/0028_add_offshore_v2_menu_context.py)
- [tests/offshore/test_offshore_ticket4_menu_context.py](../../tests/offshore/test_offshore_ticket4_menu_context.py)

## Portals

- [portal/department/api.py](../../portal/department/api.py)
- [portal/department/service.py](../../portal/department/service.py)
- [portal/department/models.py](../../portal/department/models.py)
- [portal/department/menu_choice_repo.py](../../portal/department/menu_choice_repo.py)
- [portal/department/auth.py](../../portal/department/auth.py)
- [templates/portal_department_week.html](../../templates/portal_department_week.html)
- [templates/unified_portal_week.html](../../templates/unified_portal_week.html)
- [templates/unified_portal_week_department.html](../../templates/unified_portal_week_department.html)
- [templates/unified_portal_day_department.html](../../templates/unified_portal_day_department.html)
- [tests/portal/test_department_portal_week_access.py](../../tests/portal/test_department_portal_week_access.py)
- [tests/portal/test_department_portal_menu_choice_mutation.py](../../tests/portal/test_department_portal_menu_choice_mutation.py)
- [tests/portal/test_department_portal_etag_behavior.py](../../tests/portal/test_department_portal_etag_behavior.py)

## Supporting Docs

- [docs/feature_matrix.md](../feature_matrix.md)
- [docs/legacy_functional_overview.md](../legacy_functional_overview.md)
- [docs/unified_mapping.md](../unified_mapping.md)
- [docs/platform/menu_context_architecture.md](menu_context_architecture.md)
- [docs/department_portal_week_schema.md](../department_portal_week_schema.md)
