from __future__ import annotations

from datetime import date

from sqlalchemy import text

from core.admin_repo import (
    DepartmentServiceAddonsRepo,
    DepartmentsRepo,
    DietTypesRepo,
    ServiceAddonsRepo,
    SitesRepo,
)
from core.app_factory import create_app
from core.builder_sqlite import initialize_builder_sqlite
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.commun_builder_publication import CommunBuilderPublicationService
from core.commun_builder_projection import get_shadow_projection_reader
from core.db import create_all, get_session
from core.department_menu_choice_repo import MenuChoiceRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.feature_service import FeatureService
from core.menu_service import MenuServiceDB
from core.planera_product2_page2_context import build_product2_page2_planning_context
from core.planera_product2_page3_vm import build_product2_page3_vm
from core.planning_option_review import ADAPTATION_REQUIRED, PlanningOptionReviewService
from core.weekview.repo import WeekviewRepo


TENANT_NAME = "K30 Integration Customer"
SITE_NAME = "K30 Integration Site"
SERVICE_DATE = date(2026, 11, 2)
YEAR = SERVICE_DATE.isocalendar().year
WEEK = SERVICE_DATE.isocalendar().week
MEAL = "lunch"


def _configure_builder_context(app, *, site_id: str, builder_menu_id: str, year: int, week: int) -> None:
    from flask import current_app
    from scripts.seed_product2_e2e import _build_builder_flow

    builder_flow, menu_context_flow = _build_builder_flow()
    current_app.extensions["builder_flow"] = builder_flow
    current_app.extensions["builder_menu_context_flow"] = menu_context_flow
    current_app.extensions["builder_menu_service"] = menu_context_flow._menu_service
    menu_context_flow.create_menu(
        menu_id=builder_menu_id,
        site_id=site_id,
        week_key=f"{year}-W{week:02d}",
        version=1,
        status="published",
    )
    for composition_id, title, sort_order in (
        ("k30-comp-alt1", "K30 Lunch Alt 1", 10),
        ("k30-comp-alt2", "K30 Lunch Alt 2", 20),
    ):
        builder_flow.create_composition(composition_id=composition_id, composition_name=title)
        menu_context_flow.add_composition_menu_row(
            menu_id=builder_menu_id,
            day="mon",
            meal_slot=f"{MEAL}_{'alt1' if sort_order == 10 else 'alt2'}",
            composition_id=composition_id,
            sort_order=sort_order,
        )


def test_k30_kommun_new_customer_e2e(tmp_path, monkeypatch):
    main_db_path = tmp_path / "k30_kommun_main.db"
    builder_db_path = tmp_path / "k30_kommun_builder.db"
    initialize_builder_sqlite(str(builder_db_path))

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "k30-integration-secret",
            "database_url": f"sqlite:///{main_db_path.as_posix()}",
            "BUILDER_DB_PATH": str(builder_db_path),
            "FORCE_DB_REINIT": True,
        }
    )

    print(f"EFFECTIVE_MAIN_DB={main_db_path}")
    print(f"EFFECTIVE_BUILDER_DB={builder_db_path}")
    with app.app_context():
        create_all()

        tenant_id = FeatureService().create_tenant_with_admin(
            TENANT_NAME,
            ["municipal"],
            "k30.integration@example.test",
            "k30-integration-password",
        )
        site, _ = SitesRepo().create_site(SITE_NAME, tenant_id=tenant_id)
        site_id = str(site["id"])

        fast, _ = DepartmentsRepo().create_department(
            site_id=site_id,
            name="K30 Fast",
            resident_count_mode="fixed",
            resident_count_fixed=12,
        )
        variable, _ = DepartmentsRepo().create_department(
            site_id=site_id,
            name="K30 Variable",
            resident_count_mode="variable",
            resident_count_fixed=None,
        )
        combined, _ = DepartmentsRepo().create_department(
            site_id=site_id,
            name="K30 Combined",
            resident_count_mode="fixed",
            resident_count_fixed=8,
        )

        departments = [fast, variable, combined]
        department_ids = [str(department["id"]) for department in departments]
        assert len(department_ids) == 3

        WeekviewRepo().set_residents_counts(
            tenant_id=tenant_id,
            year=YEAR,
            week=WEEK,
            department_id=str(fast["id"]),
            items=[
                {"day_of_week": 1, "meal": MEAL, "count": 12},
                {"day_of_week": 1, "meal": "dinner", "count": 12},
            ],
        )
        WeekviewRepo().set_residents_counts(
            tenant_id=tenant_id,
            year=YEAR,
            week=WEEK,
            department_id=str(variable["id"]),
            items=[
                {"day_of_week": 1, "meal": MEAL, "count": 10},
                {"day_of_week": 1, "meal": "dinner", "count": 10},
            ],
        )
        WeekviewRepo().set_residents_counts(
            tenant_id=tenant_id,
            year=YEAR,
            week=WEEK,
            department_id=str(combined["id"]),
            items=[
                {"day_of_week": 1, "meal": MEAL, "count": 8},
                {"day_of_week": 1, "meal": "dinner", "count": 8},
            ],
        )

        diet_repo = DietTypesRepo()
        timbal_id = diet_repo.create(site_id=site_id, name="Timbal", default_select=False, semantics="atomic")
        glutenfri_id = diet_repo.create(site_id=site_id, name="Glutenfri", default_select=False, semantics="atomic")
        group_repo = DepartmentRequirementGroupsRepo()
        timbal_group = group_repo.create_group(
            str(fast["id"]),
            2,
            [timbal_id],
            label="Timbal",
        )
        combined_group = group_repo.create_group(
            str(combined["id"]),
            1,
            [timbal_id, glutenfri_id],
            label="Timbal + Glutenfri",
        )

        addon_id = ServiceAddonsRepo().create_if_missing("Mos", site_id, "mos")
        DepartmentServiceAddonsRepo().add_for_department(
            str(fast["id"]),
            addon_id,
            service_scope=MEAL,
            quantity_mode="custom",
            lunch_count=3,
            dinner_count=None,
            note="Utan smör",
            site_id=site_id,
        )

        db = get_session()
        try:
            assert db.execute(text("SELECT tenant_id FROM sites WHERE id=:id"), {"id": site_id}).scalar() == tenant_id
            assert db.execute(text("SELECT COUNT(*) FROM departments WHERE site_id=:site_id"), {"site_id": site_id}).scalar() == 3
            assert db.execute(
                text("SELECT resident_count_mode FROM departments WHERE id=:id"),
                {"id": str(variable["id"])},
            ).scalar() == "variable"
        finally:
            db.close()

        builder_menu_id = "k30-integration-builder-menu"
        _configure_builder_context(
            app,
            site_id=site_id,
            builder_menu_id=builder_menu_id,
            year=YEAR,
            week=WEEK,
        )
        legacy_menu = MenuServiceDB().create_or_get_menu(tenant_id, site_id, WEEK, YEAR)
        CommunBuilderMenuLinkService().create_or_replace_link(
            tenant_id=tenant_id,
            site_id=site_id,
            year=YEAR,
            week=WEEK,
            builder_menu_id=builder_menu_id,
            legacy_menu_id=legacy_menu.id,
            source="manual",
        )
        publication = CommunBuilderPublicationService().publish_week(
            tenant_id=tenant_id,
            site_id=site_id,
            year=YEAR,
            week=WEEK,
            legacy_menu_id=legacy_menu.id,
        )
        assert publication is not None
        projection = get_shadow_projection_reader().get_projection_for_pinned_menu(
            tenant_id=tenant_id,
            site_id=site_id,
            year=YEAR,
            week=WEEK,
            builder_menu_id=builder_menu_id,
            builder_menu_version=1,
        )
        assert projection.status == "ok"
        assert projection.projection is not None

        MenuChoiceRepo().set_choice(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=str(fast["id"]),
            year=YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="alt1",
            meal=MEAL,
        )
        MenuChoiceRepo().set_choice(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=str(variable["id"]),
            year=YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="alt1",
            meal=MEAL,
        )
        MenuChoiceRepo().set_choice(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=str(combined["id"]),
            year=YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="alt1",
            meal=MEAL,
        )

        context = build_product2_page2_planning_context(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=SERVICE_DATE,
            meal=MEAL,
        )
        options = {str(option.variant_type): option for option in context.options}
        assert set(options) == {"alt1", "alt2"}
        selected_option = options["alt1"]
        destinations = {str(destination.destination_id): destination for destination in context.destinations}
        assert set(destinations) == set(department_ids)

        review = PlanningOptionReviewService().save_option_review(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=SERVICE_DATE,
            meal=MEAL,
            option_id=selected_option.option_id,
            decisions=[
                {
                    "destination_id": str(fast["id"]),
                    "requirement_group_id": str(timbal_group["id"]),
                    "decision": ADAPTATION_REQUIRED,
                },
                {
                    "destination_id": str(combined["id"]),
                    "requirement_group_id": str(combined_group["id"]),
                    "decision": ADAPTATION_REQUIRED,
                },
            ],
            reviewed_by_user_id=1,
        )
        assert review.review_state == "REVIEWED_WITH_DEVIATIONS"

        page3 = build_product2_page3_vm(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=SERVICE_DATE,
            meal=MEAL,
            option_id=selected_option.option_id,
            view="special",
            special_view="department",
        )
        assert page3.ready is True
        assert len(page3.completion_targets) == 2
        target_quantities = {str(target.requirement_group_id): int(target.quantity) for target in page3.completion_targets}
        assert target_quantities[str(timbal_group["id"])] == 2
        assert target_quantities[str(combined_group["id"])] == 1
        assert sum(target_quantities.values()) == 3
        addon_rows = [
            row
            for group in page3.special_destination_groups
            for row in group.service_addons
            if str(row.addon_id) == str(addon_id)
        ]
        assert len(addon_rows) == 1
        assert addon_rows[0].quantity_label == "3"
        assert addon_rows[0].note == "Utan smör"

        completion_repo = DepartmentRequirementGroupCompletionRepo()
        for target in page3.completion_targets:
            completion_repo.set_marked(
                str(target.destination_id),
                str(target.requirement_group_id),
                SERVICE_DATE,
                MEAL,
                True,
            )
        for target in page3.completion_targets:
            assert completion_repo.get(
                str(target.requirement_group_id),
                SERVICE_DATE,
                MEAL,
            ) == {
                "group_id": str(target.requirement_group_id),
                "service_date": SERVICE_DATE.isoformat(),
                "meal_key": MEAL,
                "marked": True,
            }

        client = app.test_client()
        report_response = client.get(
            f"/api/reports/weekview?site_id={site_id}&year={YEAR}&week={WEEK}",
            headers={"X-User-Role": "admin", "X-Tenant-Id": str(tenant_id)},
        )
        assert report_response.status_code == 200
        report_body = report_response.get_json()
        assert report_body["site_id"] == site_id
