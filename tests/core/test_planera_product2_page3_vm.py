from __future__ import annotations

import pytest

from core.planera_product2_menu_vm import Product2MealOptionVM
from core.planera_product2_page2_context import (
    Product2Page2DestinationVM,
    Product2Page2PlanningContext,
    Product2Page2PublicationIdentity,
    Product2Page2RequirementGroupVM,
    Product2Page2RequirementVM,
)
from core.planera_product2_page3_vm import build_product2_page3_vm
from core.planera_v2.domain import PlanResult, Totals, UnitBreakdown
from core.planera_v2.meal_orchestration import (
    KommunMealOptionResult,
    KommunMealOrchestrationResult,
)


def _context() -> Product2Page2PlanningContext:
    option = Product2MealOptionVM(
        option_id="option-1",
        variant_type="alt1",
        display_label="Alt 1",
        sort_order=10,
        display_title="Fläskkarré",
        composition_id="comp-1",
        resolved=True,
    )
    destination = Product2Page2DestinationVM(
        destination_id="dept-a",
        display_name="Avdelning A",
        baseline_quantity=10,
        selected_option_id="option-1",
        choice_source="explicit",
    )
    requirement_group = Product2Page2RequirementGroupVM(
        requirement_group_id="group-veg",
        destination_id="dept-a",
        label="Vegetariskt",
        effective_quantity=3,
        requirements=(
            Product2Page2RequirementVM(
                dietary_type_id=1,
                requirement_key="veg",
                name="Vegetariskt",
                semantics="atomic",
            ),
        ),
    )
    return Product2Page2PlanningContext(
        site_id="site-1",
        service_date="2026-09-08",
        meal="lunch",
        status="ok",
        publication_identity=Product2Page2PublicationIdentity(builder_menu_id="menu-1", builder_menu_version=1),
        options=(option,),
        destinations=(destination,),
        requirement_groups=(requirement_group,),
    )


def _meal_result() -> KommunMealOrchestrationResult:
    plan_result = PlanResult(
        totals=Totals(baseline_total=10, deviation_total=3, normal_total=7),
        per_combination={"special__veg": 3},
        per_unit={"dept-a": 7},
        per_unit_breakdown={
            "dept-a": UnitBreakdown(
                baseline_total=10,
                deviation_total=3,
                normal_total=7,
                per_combination={"special__veg": 3},
                per_form={"special": 3},
            )
        },
        warnings=[],
    )
    option = KommunMealOptionResult(
        option_id="option-1",
        display_title="Fläskkarré",
        assigned_destination_ids=("dept-a",),
        assigned_destination_count=1,
        has_demand=True,
        requires_review=True,
        review_state="ready",
        review_is_stale=False,
        blockers=(),
        planning_slice=None,
        plan_result=plan_result,
        acceptance_issues=(),
    )
    return KommunMealOrchestrationResult(
        tenant_id=1,
        site_id="site-1",
        service_date="2026-09-08",
        meal="lunch",
        publication_identity=None,
        options=(option,),
        unassigned_destinations=(),
        blockers=(),
        ready=True,
    )


def _meal_result_with_option(
    *,
    plan_result: PlanResult | None,
    blockers: tuple[str, ...] = (),
    has_demand: bool = True,
    option_id: str = "option-1",
    display_title: str = "Fläskkarré",
    assigned_destination_ids: tuple[str, ...] = ("dept-a",),
    assigned_destination_count: int = 1,
) -> KommunMealOrchestrationResult:
    option = KommunMealOptionResult(
        option_id=option_id,
        display_title=display_title,
        assigned_destination_ids=assigned_destination_ids,
        assigned_destination_count=assigned_destination_count,
        has_demand=has_demand,
        requires_review=has_demand,
        review_state=None,
        review_is_stale=False,
        blockers=blockers,
        planning_slice=None,
        plan_result=plan_result,
        acceptance_issues=(),
    )
    return KommunMealOrchestrationResult(
        tenant_id=1,
        site_id="site-1",
        service_date="2026-09-08",
        meal="lunch",
        publication_identity=None,
        options=(option,),
        unassigned_destinations=(),
        blockers=blockers,
        ready=not blockers,
    )


def test_build_product2_page3_vm_uses_orchestration_numbers_and_page2_metadata(monkeypatch):
    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", lambda **_: _context())
    monkeypatch.setattr("core.planera_product2_page3_vm.run_kommun_meal_orchestration", lambda **_: _meal_result())

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")

    assert vm.site_name == "Avdelningarnas kök"
    assert vm.ready is True
    assert vm.ready_label == "Underlag granskat"
    assert vm.page2_url == "/ui/kitchen/planering/day?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch"
    assert vm.options[0].display_label == "Alt 1"
    assert vm.options[0].baseline_total == 10
    assert vm.options[0].normal_total == 7
    assert vm.options[0].special_total == 3
    assert [row.display_name for row in vm.options[0].normal_department_rows] == ["Avdelning A"]
    assert vm.options[0].special_cohorts[0].label == "Vegetariskt"
    assert vm.options[0].special_cohorts[0].department_quantities[0].quantity == 3


def test_build_product2_page3_vm_overview_and_normal_matrix_projection(monkeypatch):
    def _page2_context(**_kwargs):
        option_1 = Product2MealOptionVM(
            option_id="option-1",
            variant_type="alt1",
            display_label="Alt 1",
            sort_order=10,
            display_title="Vardagsgryta med rotfrukter",
            composition_id="comp-1",
            resolved=True,
        )
        option_2 = Product2MealOptionVM(
            option_id="option-2",
            variant_type="alt2",
            display_label="Alt 2",
            sort_order=20,
            display_title="Ugnsbakad fisk med dill",
            composition_id="comp-2",
            resolved=True,
        )
        destination_1 = Product2Page2DestinationVM(
            destination_id="dept-a",
            display_name="Avdelning 01",
            baseline_quantity=79,
            selected_option_id="option-1",
            choice_source="explicit",
        )
        destination_2 = Product2Page2DestinationVM(
            destination_id="dept-b",
            display_name="Avdelning 11",
            baseline_quantity=62,
            selected_option_id="option-2",
            choice_source="explicit",
        )
        requirement_group = Product2Page2RequirementGroupVM(
            requirement_group_id="group-timbal",
            destination_id="dept-b",
            label="Timbal",
            effective_quantity=1,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=1,
                    requirement_key="timbal",
                    name="Timbal",
                    semantics="atomic",
                ),
            ),
        )
        return Product2Page2PlanningContext(
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            status="ok",
            publication_identity=Product2Page2PublicationIdentity(builder_menu_id="menu-1", builder_menu_version=1),
            options=(option_1, option_2),
            destinations=(destination_1, destination_2),
            requirement_groups=(requirement_group,),
        )

    option_1_plan = PlanResult(
        totals=Totals(baseline_total=79, deviation_total=0, normal_total=79),
        per_combination={},
        per_unit={"dept-a": 79, "dept-b": 0},
        per_unit_breakdown={
            "dept-a": UnitBreakdown(baseline_total=79, deviation_total=0, normal_total=79, per_combination={}, per_form={}),
            "dept-b": UnitBreakdown(baseline_total=0, deviation_total=0, normal_total=0, per_combination={}, per_form={}),
        },
        warnings=[],
    )
    option_2_plan = PlanResult(
        totals=Totals(baseline_total=62, deviation_total=8, normal_total=54),
        per_combination={"special__timbal": 8},
        per_unit={"dept-a": 0, "dept-b": 54},
        per_unit_breakdown={
            "dept-a": UnitBreakdown(baseline_total=0, deviation_total=0, normal_total=0, per_combination={"special__timbal": 0}, per_form={}),
            "dept-b": UnitBreakdown(baseline_total=62, deviation_total=8, normal_total=54, per_combination={"special__timbal": 8}, per_form={"special": 8}),
        },
        warnings=[],
    )

    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", _page2_context)
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: KommunMealOrchestrationResult(
            tenant_id=1,
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            publication_identity=None,
            options=(
                KommunMealOptionResult(
                    option_id="option-1",
                    display_title="Vardagsgryta med rotfrukter",
                    assigned_destination_ids=("dept-a",),
                    assigned_destination_count=1,
                    has_demand=True,
                    requires_review=True,
                    review_state="ready",
                    review_is_stale=False,
                    blockers=(),
                    planning_slice=None,
                    plan_result=option_1_plan,
                    acceptance_issues=(),
                ),
                KommunMealOptionResult(
                    option_id="option-2",
                    display_title="Ugnsbakad fisk med dill",
                    assigned_destination_ids=("dept-b",),
                    assigned_destination_count=1,
                    has_demand=True,
                    requires_review=True,
                    review_state="ready",
                    review_is_stale=False,
                    blockers=(),
                    planning_slice=None,
                    plan_result=option_2_plan,
                    acceptance_issues=(),
                ),
            ),
            unassigned_destinations=(),
            blockers=(),
            ready=True,
        ),
    )

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")

    assert [option.display_title for option in vm.overview_options] == ["Vardagsgryta med rotfrukter", "Ugnsbakad fisk med dill"]
    assert vm.overview_options[0].baseline_total == 79
    assert vm.overview_options[0].normal_total == 79
    assert vm.overview_options[0].special_total == 0
    assert vm.overview_options[1].baseline_total == 62
    assert vm.overview_options[1].normal_total == 54
    assert vm.overview_options[1].special_total == 8

    assert [column.display_title for column in vm.normal_matrix.columns] == ["Vardagsgryta med rotfrukter", "Ugnsbakad fisk med dill"]
    assert vm.normal_matrix.rows[0].display_name == "Avdelning 01"
    assert vm.normal_matrix.rows[0].cells[0].display_value == "79"
    assert vm.normal_matrix.rows[0].cells[1].display_value == "—"
    assert vm.normal_matrix.rows[1].cells[0].display_value == "—"
    assert vm.normal_matrix.rows[1].cells[1].display_value == "54"
    assert [total.display_total for total in vm.normal_matrix.totals] == ["79", "54"]


def test_build_product2_page3_vm_special_production_and_destination_views_group_exact_cohorts(monkeypatch):
    def _page2_context(**_kwargs):
        option_1 = Product2MealOptionVM(
            option_id="option-1",
            variant_type="alt1",
            display_label="Alt 1",
            sort_order=10,
            display_title="Vardagsgryta med rotfrukter",
            composition_id="comp-1",
            resolved=True,
        )
        option_2 = Product2MealOptionVM(
            option_id="option-2",
            variant_type="alt2",
            display_label="Alt 2",
            sort_order=20,
            display_title="Ugnsbakad fisk med dill",
            composition_id="comp-2",
            resolved=True,
        )
        destination_1 = Product2Page2DestinationVM(
            destination_id="dept-a",
            display_name="Avdelning 16",
            baseline_quantity=10,
            selected_option_id="option-1",
            choice_source="explicit",
        )
        destination_2 = Product2Page2DestinationVM(
            destination_id="dept-b",
            display_name="Avdelning 11",
            baseline_quantity=12,
            selected_option_id="option-2",
            choice_source="explicit",
        )
        requirement_group_timbal = Product2Page2RequirementGroupVM(
            requirement_group_id="group-timbal",
            destination_id="dept-a",
            label="Timbal",
            effective_quantity=1,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=1,
                    requirement_key="timbal",
                    name="Timbal",
                    semantics="atomic",
                ),
            ),
        )
        requirement_group_glutenfri = Product2Page2RequirementGroupVM(
            requirement_group_id="group-glutenfri",
            destination_id="dept-b",
            label="Glutenfri",
            effective_quantity=1,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=2,
                    requirement_key="glutenfri",
                    name="Glutenfri",
                    semantics="atomic",
                ),
            ),
        )
        return Product2Page2PlanningContext(
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            status="ok",
            publication_identity=Product2Page2PublicationIdentity(builder_menu_id="menu-1", builder_menu_version=1),
            options=(option_1, option_2),
            destinations=(destination_1, destination_2),
            requirement_groups=(requirement_group_timbal, requirement_group_glutenfri),
        )

    option_1_plan = PlanResult(
        totals=Totals(baseline_total=20, deviation_total=2, normal_total=18),
        per_combination={"special__timbal__glutenfri": 2},
        per_unit={"dept-a": 18},
        per_unit_breakdown={
            "dept-a": UnitBreakdown(baseline_total=20, deviation_total=2, normal_total=18, per_combination={"special__timbal__glutenfri": 2}, per_form={"special": 2}),
        },
        warnings=[],
    )
    option_2_plan = PlanResult(
        totals=Totals(baseline_total=15, deviation_total=1, normal_total=14),
        per_combination={"special__timbal__glutenfri": 1},
        per_unit={"dept-b": 14},
        per_unit_breakdown={
            "dept-b": UnitBreakdown(baseline_total=15, deviation_total=1, normal_total=14, per_combination={"special__timbal__glutenfri": 1}, per_form={"special": 1}),
        },
        warnings=[],
    )

    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", _page2_context)
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: KommunMealOrchestrationResult(
            tenant_id=1,
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            publication_identity=None,
            options=(
                KommunMealOptionResult(
                    option_id="option-1",
                    display_title="Vardagsgryta med rotfrukter",
                    assigned_destination_ids=("dept-a",),
                    assigned_destination_count=1,
                    has_demand=True,
                    requires_review=True,
                    review_state="ready",
                    review_is_stale=False,
                    blockers=(),
                    planning_slice=None,
                    plan_result=option_1_plan,
                    acceptance_issues=(),
                ),
                KommunMealOptionResult(
                    option_id="option-2",
                    display_title="Ugnsbakad fisk med dill",
                    assigned_destination_ids=("dept-b",),
                    assigned_destination_count=1,
                    has_demand=True,
                    requires_review=True,
                    review_state="ready",
                    review_is_stale=False,
                    blockers=(),
                    planning_slice=None,
                    plan_result=option_2_plan,
                    acceptance_issues=(),
                ),
            ),
            unassigned_destinations=(),
            blockers=(),
            ready=True,
        ),
    )

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")

    assert vm.special_production_groups[0].label == "Timbal + Glutenfri"
    assert vm.special_production_groups[0].quantity == 3
    assert [dish.display_title for dish in vm.special_production_groups[0].dishes] == ["Vardagsgryta med rotfrukter", "Ugnsbakad fisk med dill"]
    assert [dish.quantity for dish in vm.special_production_groups[0].dishes] == [2, 1]

    assert vm.special_destination_groups[0].display_name == "Avdelning 16"
    assert vm.special_destination_groups[0].rows[0].label == "Timbal + Glutenfri"
    assert vm.special_destination_groups[0].rows[0].quantity == 2
    assert [dish.quantity for dish in vm.special_destination_groups[0].rows[0].dishes] == [2]

    assert vm.special_destination_groups[1].display_name == "Avdelning 11"
    assert vm.special_destination_groups[1].rows[0].label == "Timbal + Glutenfri"
    assert vm.special_destination_groups[1].rows[0].quantity == 1
    assert [dish.quantity for dish in vm.special_destination_groups[1].rows[0].dishes] == [1]


def test_build_product2_page3_vm_combines_multi_key_cohort_and_uses_canonical_names(monkeypatch):
    def _page2_context(**_kwargs):
        option = Product2MealOptionVM(
            option_id="option-1",
            variant_type="alt1",
            display_label="Alt 1",
            sort_order=10,
            display_title="Fläskkarré",
            composition_id="comp-1",
            resolved=True,
        )
        destination = Product2Page2DestinationVM(
            destination_id="dept-a",
            display_name="Avdelning A",
            baseline_quantity=18,
            selected_option_id="option-1",
            choice_source="explicit",
        )
        requirement_group_gluten = Product2Page2RequirementGroupVM(
            requirement_group_id="group-gluten",
            destination_id="dept-a",
            label="Glutenfri",
            effective_quantity=1,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=1,
                    requirement_key="glutenfri",
                    name="Glutenfri",
                    semantics="atomic",
                ),
            ),
        )
        requirement_group_laktos = Product2Page2RequirementGroupVM(
            requirement_group_id="group-laktos",
            destination_id="dept-a",
            label="Laktosfri",
            effective_quantity=1,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=2,
                    requirement_key="laktosfri",
                    name="Laktosfri",
                    semantics="atomic",
                ),
            ),
        )
        return Product2Page2PlanningContext(
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            status="ok",
            publication_identity=Product2Page2PublicationIdentity(builder_menu_id="menu-1", builder_menu_version=1),
            options=(option,),
            destinations=(destination,),
            requirement_groups=(requirement_group_gluten, requirement_group_laktos),
        )

    plan_result = PlanResult(
        totals=Totals(baseline_total=18, deviation_total=2, normal_total=16),
        per_combination={"special__glutenfri__laktosfri": 2},
        per_unit={"dept-a": 16},
        per_unit_breakdown={
            "dept-a": UnitBreakdown(
                baseline_total=18,
                deviation_total=2,
                normal_total=16,
                per_combination={"special__glutenfri__laktosfri": 2},
                per_form={"special": 2},
            )
        },
        warnings=[],
    )

    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", _page2_context)
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: _meal_result_with_option(plan_result=plan_result),
    )

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")

    assert vm.options[0].baseline_total == 18
    assert vm.options[0].normal_total == 16
    assert vm.options[0].special_total == 2
    assert vm.options[0].normal_department_rows[0].display_name == "Avdelning A"
    assert vm.options[0].special_cohorts[0].label == "Glutenfri + Laktosfri"
    assert vm.options[0].special_cohorts[0].quantity == 2
    assert vm.options[0].special_cohorts[0].department_quantities[0].display_name == "Avdelning A"


def test_build_product2_page3_vm_filters_empty_special_destination_groups_and_keeps_order(monkeypatch):
    def _page2_context(**_kwargs):
        option = Product2MealOptionVM(
            option_id="option-1",
            variant_type="alt1",
            display_label="Alt 1",
            sort_order=10,
            display_title="Vardagsgryta med rotfrukter",
            composition_id="comp-1",
            resolved=True,
        )
        destination_a = Product2Page2DestinationVM(
            destination_id="dept-a",
            display_name="Avdelning A",
            baseline_quantity=10,
            selected_option_id="option-1",
            choice_source="explicit",
        )
        destination_b = Product2Page2DestinationVM(
            destination_id="dept-b",
            display_name="Avdelning B",
            baseline_quantity=20,
            selected_option_id="option-1",
            choice_source="explicit",
        )
        destination_c = Product2Page2DestinationVM(
            destination_id="dept-c",
            display_name="Avdelning C",
            baseline_quantity=30,
            selected_option_id="option-1",
            choice_source="explicit",
        )
        requirement_group_b = Product2Page2RequirementGroupVM(
            requirement_group_id="group-b",
            destination_id="dept-b",
            label="Glutenfri",
            effective_quantity=2,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=1,
                    requirement_key="glutenfri",
                    name="Glutenfri",
                    semantics="atomic",
                ),
            ),
        )
        requirement_group_c = Product2Page2RequirementGroupVM(
            requirement_group_id="group-c",
            destination_id="dept-c",
            label="Laktosfri",
            effective_quantity=3,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=2,
                    requirement_key="laktosfri",
                    name="Laktosfri",
                    semantics="atomic",
                ),
            ),
        )
        return Product2Page2PlanningContext(
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            status="ok",
            publication_identity=Product2Page2PublicationIdentity(builder_menu_id="menu-1", builder_menu_version=1),
            options=(option,),
            destinations=(destination_a, destination_b, destination_c),
            requirement_groups=(requirement_group_b, requirement_group_c),
        )

    plan_result = PlanResult(
        totals=Totals(baseline_total=60, deviation_total=5, normal_total=55),
        per_combination={"special__glutenfri": 2, "special__laktosfri": 3},
        per_unit={"dept-a": 20, "dept-b": 15, "dept-c": 20},
        per_unit_breakdown={
            "dept-a": UnitBreakdown(baseline_total=10, deviation_total=0, normal_total=10, per_combination={}, per_form={}),
            "dept-b": UnitBreakdown(baseline_total=20, deviation_total=2, normal_total=18, per_combination={"special__glutenfri": 2}, per_form={"special": 2}),
            "dept-c": UnitBreakdown(baseline_total=30, deviation_total=3, normal_total=27, per_combination={"special__laktosfri": 3}, per_form={"special": 3}),
        },
        warnings=[],
    )

    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", _page2_context)
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: _meal_result_with_option(plan_result=plan_result),
    )

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch", view="special", special_view="department")

    assert [destination.display_name for destination in vm.special_destination_groups] == ["Avdelning B", "Avdelning C"]
    assert all(destination.display_name != "Avdelning A" for destination in vm.special_destination_groups)
    assert [row.label for row in vm.special_destination_groups[0].rows] == ["Glutenfri"]
    assert [row.label for row in vm.special_destination_groups[1].rows] == ["Laktosfri"]


def test_build_product2_page3_vm_zero_demand_option_stays_visible_without_invented_totals(monkeypatch):
    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", lambda **_: _context())
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: _meal_result_with_option(plan_result=None, has_demand=False, assigned_destination_ids=(), assigned_destination_count=0),
    )

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")

    assert vm.options[0].has_demand is False
    assert vm.options[0].status_label == "Inga avdelningar har valt denna rätt."
    assert vm.options[0].baseline_total is None
    assert vm.options[0].normal_total is None
    assert vm.options[0].special_total is None
    assert vm.options[0].normal_department_rows == ()
    assert vm.options[0].special_cohorts == ()


@pytest.mark.parametrize("blocker_code,status_label", [
    ("UNREVIEWED_OPTIONS", "Granskning krävs"),
    ("STALE_REVIEWS", "Granskningen behöver göras om"),
    ("INVALID_OPTION_PLAN", "Produktionsunderlag kan inte beräknas"),
])
def test_build_product2_page3_vm_blocked_options_have_no_production_quantities(monkeypatch, blocker_code, status_label):
    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", lambda **_: _context())
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: _meal_result_with_option(plan_result=None, blockers=(blocker_code,)),
    )

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")

    assert vm.options[0].status_label == status_label
    assert vm.options[0].baseline_total is None
    assert vm.options[0].normal_total is None
    assert vm.options[0].special_total is None
    assert vm.options[0].normal_department_rows == ()
    assert vm.options[0].special_cohorts == ()


def test_build_product2_page3_vm_missing_requirement_mapping_fails_closed(monkeypatch):
    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", lambda **_: _context())
    plan_result = PlanResult(
        totals=Totals(baseline_total=18, deviation_total=2, normal_total=16),
        per_combination={"special__okänd": 2},
        per_unit={"dept-a": 16},
        per_unit_breakdown={"dept-a": UnitBreakdown(baseline_total=18, deviation_total=2, normal_total=16, per_combination={"special__okänd": 2}, per_form={"special": 2})},
        warnings=[],
    )
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: _meal_result_with_option(plan_result=plan_result),
    )

    with pytest.raises(Exception, match="requirement_label_missing:okänd"):
        build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")


def test_build_product2_page3_vm_missing_destination_mapping_fails_closed(monkeypatch):
    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")

    def _page2_context_missing_destination(**_kwargs):
        ctx = _context()
        return Product2Page2PlanningContext(
            site_id=ctx.site_id,
            service_date=ctx.service_date,
            meal=ctx.meal,
            status=ctx.status,
            publication_identity=ctx.publication_identity,
            options=ctx.options,
            destinations=(),
            requirement_groups=ctx.requirement_groups,
        )

    plan_result = PlanResult(
        totals=Totals(baseline_total=18, deviation_total=2, normal_total=16),
        per_combination={"special__veg": 2},
        per_unit={"dept-b": 16},
        per_unit_breakdown={"dept-b": UnitBreakdown(baseline_total=18, deviation_total=2, normal_total=16, per_combination={"special__veg": 2}, per_form={"special": 2})},
        warnings=[],
    )
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", _page2_context_missing_destination)
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: _meal_result_with_option(plan_result=plan_result),
    )

    with pytest.raises(Exception, match="destination_missing:dept-b"):
        build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")


def test_build_product2_page3_vm_unassigned_destinations_stay_unallocated(monkeypatch):
    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    def _page2_context(**_kwargs):
        option = Product2MealOptionVM(
            option_id="option-1",
            variant_type="alt1",
            display_label="Alt 1",
            sort_order=10,
            display_title="Fläskkarré",
            composition_id="comp-1",
            resolved=True,
        )
        assigned = Product2Page2DestinationVM(
            destination_id="dept-a",
            display_name="Avdelning A",
            baseline_quantity=18,
            selected_option_id="option-1",
            choice_source="explicit",
        )
        unassigned = Product2Page2DestinationVM(
            destination_id="dept-unassigned",
            display_name="Avdelning C",
            baseline_quantity=4,
            selected_option_id=None,
            choice_source="none",
        )
        requirement_group = Product2Page2RequirementGroupVM(
            requirement_group_id="group-veg",
            destination_id="dept-a",
            label="Vegetariskt",
            effective_quantity=3,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=1,
                    requirement_key="veg",
                    name="Vegetariskt",
                    semantics="atomic",
                ),
            ),
        )
        return Product2Page2PlanningContext(
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            status="ok",
            publication_identity=Product2Page2PublicationIdentity(builder_menu_id="menu-1", builder_menu_version=1),
            options=(option,),
            destinations=(assigned, unassigned),
            requirement_groups=(requirement_group,),
        )

    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", _page2_context)

    plan_result = PlanResult(
        totals=Totals(baseline_total=18, deviation_total=3, normal_total=15),
        per_combination={"special__veg": 3},
        per_unit={"dept-a": 15},
        per_unit_breakdown={"dept-a": UnitBreakdown(baseline_total=18, deviation_total=3, normal_total=15, per_combination={"special__veg": 3}, per_form={"special": 3})},
        warnings=[],
    )
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: KommunMealOrchestrationResult(
            tenant_id=1,
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            publication_identity=None,
            options=(
                KommunMealOptionResult(
                    option_id="option-1",
                    display_title="Fläskkarré",
                    assigned_destination_ids=("dept-a",),
                    assigned_destination_count=1,
                    has_demand=True,
                    requires_review=True,
                    review_state="ready",
                    review_is_stale=False,
                    blockers=(),
                    planning_slice=None,
                    plan_result=plan_result,
                    acceptance_issues=(),
                ),
            ),
            unassigned_destinations=(
                __import__("core.planera_v2.meal_orchestration", fromlist=["KommunMealDestinationResult"]).KommunMealDestinationResult(
                    destination_id="dept-unassigned",
                    display_name="Avdelning C",
                    baseline_quantity=4,
                    selected_option_id=None,
                    choice_source="none",
                ),
            ),
            blockers=("UNASSIGNED_DESTINATIONS",),
            ready=False,
        ),
    )

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")

    assert vm.blocker_messages == ("Följande avdelningar saknar menyval",)
    assert vm.unassigned_destinations[0].display_name == "Avdelning C"
    assert vm.unassigned_destinations[0].baseline_quantity == 4
    assert vm.options[0].normal_total == 15


def test_build_product2_page3_vm_partially_blocked_meal_keeps_ready_option_visible(monkeypatch):
    def _page2_context(**_kwargs):
        option_ready = Product2MealOptionVM(
            option_id="option-ready",
            variant_type="alt1",
            display_label="Alt 1",
            sort_order=10,
            display_title="Fläskkarré",
            composition_id="comp-ready",
            resolved=True,
        )
        option_blocked = Product2MealOptionVM(
            option_id="option-blocked",
            variant_type="alt2",
            display_label="Alt 2",
            sort_order=20,
            display_title="Vegogryta",
            composition_id="comp-blocked",
            resolved=True,
        )
        destination_ready = Product2Page2DestinationVM(
            destination_id="dept-ready",
            display_name="Avdelning A",
            baseline_quantity=18,
            selected_option_id="option-ready",
            choice_source="explicit",
        )
        destination_blocked = Product2Page2DestinationVM(
            destination_id="dept-blocked",
            display_name="Avdelning B",
            baseline_quantity=12,
            selected_option_id="option-blocked",
            choice_source="explicit",
        )
        requirement_group = Product2Page2RequirementGroupVM(
            requirement_group_id="group-veg",
            destination_id="dept-ready",
            label="Vegetariskt",
            effective_quantity=3,
            requirements=(
                Product2Page2RequirementVM(
                    dietary_type_id=1,
                    requirement_key="veg",
                    name="Vegetariskt",
                    semantics="atomic",
                ),
            ),
        )
        return Product2Page2PlanningContext(
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            status="ok",
            publication_identity=Product2Page2PublicationIdentity(builder_menu_id="menu-1", builder_menu_version=1),
            options=(option_ready, option_blocked),
            destinations=(destination_ready, destination_blocked),
            requirement_groups=(requirement_group,),
        )

    ready_plan_result = PlanResult(
        totals=Totals(baseline_total=18, deviation_total=3, normal_total=15),
        per_combination={"special__veg": 3},
        per_unit={"dept-ready": 15},
        per_unit_breakdown={
            "dept-ready": UnitBreakdown(
                baseline_total=18,
                deviation_total=3,
                normal_total=15,
                per_combination={"special__veg": 3},
                per_form={"special": 3},
            )
        },
        warnings=[],
    )

    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    monkeypatch.setattr("core.planera_product2_page3_vm.build_product2_page2_planning_context", _page2_context)
    monkeypatch.setattr(
        "core.planera_product2_page3_vm.run_kommun_meal_orchestration",
        lambda **_: KommunMealOrchestrationResult(
            tenant_id=1,
            site_id="site-1",
            service_date="2026-09-08",
            meal="lunch",
            publication_identity=None,
            options=(
                KommunMealOptionResult(
                    option_id="option-ready",
                    display_title="Fläskkarré",
                    assigned_destination_ids=("dept-ready",),
                    assigned_destination_count=1,
                    has_demand=True,
                    requires_review=True,
                    review_state="ready",
                    review_is_stale=False,
                    blockers=(),
                    planning_slice=None,
                    plan_result=ready_plan_result,
                    acceptance_issues=(),
                ),
                KommunMealOptionResult(
                    option_id="option-blocked",
                    display_title="Vegogryta",
                    assigned_destination_ids=("dept-blocked",),
                    assigned_destination_count=1,
                    has_demand=True,
                    requires_review=True,
                    review_state=None,
                    review_is_stale=False,
                    blockers=("UNREVIEWED_OPTIONS",),
                    planning_slice=None,
                    plan_result=None,
                    acceptance_issues=(),
                ),
            ),
            unassigned_destinations=(),
            blockers=("UNREVIEWED_OPTIONS",),
            ready=False,
        ),
    )

    vm = build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="lunch")

    ready_option = next(option for option in vm.options if option.option_id == "option-ready")
    blocked_option = next(option for option in vm.options if option.option_id == "option-blocked")
    assert ready_option.normal_total == 15
    assert ready_option.special_total == 3
    assert blocked_option.status_label == "Granskning krävs"
    assert blocked_option.baseline_total is None
    assert blocked_option.normal_total is None
    assert blocked_option.special_total is None


def test_build_product2_page3_vm_rejects_non_lunch(monkeypatch):
    monkeypatch.setattr("core.planera_product2_page3_vm._load_site_name", lambda **_: "Avdelningarnas kök")
    with pytest.raises(ValueError, match="meal_unsupported"):
        build_product2_page3_vm(tenant_id=1, site_id="site-1", service_date="2026-09-08", meal="dinner")