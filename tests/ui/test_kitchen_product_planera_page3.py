from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

from core.admin_repo import DepartmentServiceAddonsRepo, DepartmentsRepo, ServiceAddonsRepo, SitesRepo
from core.db import get_session
from sqlalchemy import text
from core.planera_product2_page3_vm import (
    Product2Page3CompletionTargetVM,
    Product2Page3DepartmentQuantityVM,
    Product2Page3DestinationVM,
    Product2Page3NormalMatrixCellVM,
    Product2Page3NormalMatrixColumnVM,
    Product2Page3NormalMatrixRowVM,
    Product2Page3NormalMatrixVM,
    Product2Page3OptionVM,
    Product2Page3SpecialDestinationDishVM,
    Product2Page3SpecialDestinationGroupVM,
    Product2Page3SpecialDestinationRowVM,
    Product2Page3SpecialDishVM,
    Product2Page3SpecialProductionGroupVM,
    Product2Page3SpecialCohortVM,
    Product2Page3VM,
)


def _tag_has_hidden(html: str, marker: str) -> bool:
    return bool(re.search(rf"{re.escape(marker)}[^>]*hidden", html))


def _page3_vm() -> Product2Page3VM:
    normal_matrix = Product2Page3NormalMatrixVM(
        columns=(
            Product2Page3NormalMatrixColumnVM(
                option_id="option-1",
                display_title="Fläskkarré",
                total=7,
                display_total="7",
            ),
        ),
        rows=(
            Product2Page3NormalMatrixRowVM(
                destination_id="dept-a",
                display_name="Avdelning A",
                cells=(
                    Product2Page3NormalMatrixCellVM(
                        option_id="option-1",
                        quantity=7,
                        display_value="7",
                    ),
                ),
            ),
        ),
        totals=(
            Product2Page3NormalMatrixColumnVM(
                option_id="option-1",
                display_title="Fläskkarré",
                total=7,
                display_total="7",
            ),
        ),
    )
    special_production_groups = (
        Product2Page3SpecialProductionGroupVM(
            combination_key="special__veg",
            label="Vegetariskt",
            quantity=3,
            dishes=(
                Product2Page3SpecialDishVM(
                    option_id="option-1",
                    display_title="Fläskkarré",
                    quantity=3,
                    department_quantities=(
                            Product2Page3DepartmentQuantityVM(
                                destination_id="dept-a",
                                display_name="Avdelning A",
                                quantity=3,
                            ),
                    ),
                ),
            ),
        ),
    )
    special_destination_groups = (
        Product2Page3SpecialDestinationGroupVM(
            destination_id="dept-a",
            display_name="Avdelning A",
            rows=(
                Product2Page3SpecialDestinationRowVM(
                    combination_key="special__veg",
                    label="Vegetariskt",
                    quantity=3,
                    dishes=(
                        Product2Page3SpecialDestinationDishVM(
                            option_id="option-1",
                            display_title="Fläskkarré",
                            quantity=3,
                        ),
                    ),
                ),
            ),
        ),
    )
    return Product2Page3VM(
        tenant_id=1,
        site_id="site-1",
        site_name="Kommunköket",
        service_date="2026-09-08",
        service_date_label="tisdag 8 sep 2026",
        meal="lunch",
        meal_label="Lunch",
        ready=True,
        ready_label="Produktionsunderlaget är klart",
        blockers=(),
        blocker_messages=(),
        view="overview",
        special_view="production",
        overview_options=(
            Product2Page3OptionVM(
                option_id="option-1",
                display_label="Alt 1",
                display_title="Fläskkarré",
                has_demand=True,
                status_label=None,
                blockers=(),
                baseline_total=10,
                normal_total=7,
                special_total=3,
                normal_department_rows=(
                    Product2Page3DestinationVM(
                        destination_id="dept-a",
                        display_name="Avdelning A",
                        baseline_quantity=10,
                    ),
                ),
                special_cohorts=(
                    Product2Page3SpecialCohortVM(
                        label="Vegetariskt",
                        quantity=3,
                        department_quantities=(
                            Product2Page3DepartmentQuantityVM(
                                destination_id="dept-a",
                                display_name="Avdelning A",
                                quantity=3,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        normal_matrix=normal_matrix,
        special_production_groups=special_production_groups,
        special_destination_groups=special_destination_groups,
        page1_url="/ui/kitchen/planering?ui=product2&site_id=site-1&year=2026&week=37&day=1",
        page2_url="/ui/kitchen/planering/day?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&option_id=option-1",
        navigation_urls={
            "overview": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=overview",
            "normal": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=normal",
            "special": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=special&special_view=production",
        },
        special_navigation_urls={
            "production": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=special&special_view=production",
            "department": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=special&special_view=department",
        },
        publication_identity=object(),
        options=(
            Product2Page3OptionVM(
                option_id="option-1",
                display_label="Alt 1",
                display_title="Fläskkarré",
                has_demand=True,
                status_label=None,
                blockers=(),
                baseline_total=10,
                normal_total=7,
                special_total=3,
                normal_department_rows=(
                    Product2Page3DestinationVM(
                        destination_id="dept-a",
                        display_name="Avdelning A",
                        baseline_quantity=10,
                    ),
                ),
                special_cohorts=(
                    Product2Page3SpecialCohortVM(
                        label="Vegetariskt",
                        quantity=3,
                        department_quantities=(
                            Product2Page3DestinationVM(
                                destination_id="dept-a",
                                display_name="Avdelning A",
                                baseline_quantity=3,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        unassigned_destinations=(),
    )


def _page3_vm_hierarchy(*, view: str = "overview", special_view: str = "production", ready: bool = True, blocker_messages: tuple[str, ...] = ()) -> Product2Page3VM:
    normal_matrix = Product2Page3NormalMatrixVM(
        columns=(
            Product2Page3NormalMatrixColumnVM(
                option_id="option-1",
                display_title="Vardagsgryta med rotfrukter",
                total=79,
                display_total="79",
            ),
            Product2Page3NormalMatrixColumnVM(
                option_id="option-2",
                display_title="Ugnsbakad fisk med dill",
                total=54,
                display_total="54",
            ),
        ),
        rows=(
            Product2Page3NormalMatrixRowVM(
                destination_id="dept-01",
                display_name="Avdelning 01",
                cells=(
                    Product2Page3NormalMatrixCellVM(option_id="option-1", quantity=5, display_value="5"),
                    Product2Page3NormalMatrixCellVM(option_id="option-2", quantity=None, display_value="—"),
                ),
            ),
            Product2Page3NormalMatrixRowVM(
                destination_id="dept-11",
                display_name="Avdelning 11",
                cells=(
                    Product2Page3NormalMatrixCellVM(option_id="option-1", quantity=None, display_value="—"),
                    Product2Page3NormalMatrixCellVM(option_id="option-2", quantity=7, display_value="7"),
                ),
            ),
        ),
        totals=(
            Product2Page3NormalMatrixColumnVM(
                option_id="option-1",
                display_title="Vardagsgryta med rotfrukter",
                total=79,
                display_total="79",
            ),
            Product2Page3NormalMatrixColumnVM(
                option_id="option-2",
                display_title="Ugnsbakad fisk med dill",
                total=54,
                display_total="54",
            ),
        ),
    )
    special_production_groups = (
        Product2Page3SpecialProductionGroupVM(
            combination_key="special__glutenfri",
            label="Glutenfri",
            quantity=4,
            dishes=(
                Product2Page3SpecialDishVM(
                    option_id="option-2",
                    display_title="Ugnsbakad fisk med dill",
                    quantity=4,
                    department_quantities=(
                        Product2Page3DepartmentQuantityVM(destination_id="dept-11", display_name="Avdelning 11", quantity=1),
                        Product2Page3DepartmentQuantityVM(destination_id="dept-16", display_name="Avdelning 16", quantity=3),
                    ),
                ),
            ),
        ),
        Product2Page3SpecialProductionGroupVM(
            combination_key="special__timbal",
            label="Timbal",
            quantity=7,
            dishes=(
                Product2Page3SpecialDishVM(
                    option_id="option-1",
                    display_title="Vardagsgryta med rotfrukter",
                    quantity=4,
                    department_quantities=(
                        Product2Page3DepartmentQuantityVM(destination_id="dept-01", display_name="Avdelning 01", quantity=2),
                        Product2Page3DepartmentQuantityVM(destination_id="dept-04", display_name="Avdelning 04", quantity=2),
                    ),
                ),
                Product2Page3SpecialDishVM(
                    option_id="option-2",
                    display_title="Ugnsbakad fisk med dill",
                    quantity=3,
                    department_quantities=(
                        Product2Page3DepartmentQuantityVM(destination_id="dept-12", display_name="Avdelning 12", quantity=1),
                        Product2Page3DepartmentQuantityVM(destination_id="dept-16", display_name="Avdelning 16", quantity=2),
                    ),
                ),
            ),
        ),
    )
    special_destination_groups = (
        Product2Page3SpecialDestinationGroupVM(
            destination_id="dept-11",
            display_name="Avdelning 11",
            rows=(
                Product2Page3SpecialDestinationRowVM(
                    combination_key="special__glutenfri",
                    label="Glutenfri",
                    quantity=4,
                    dishes=(
                        Product2Page3SpecialDestinationDishVM(option_id="option-2", display_title="Ugnsbakad fisk med dill", quantity=4),
                    ),
                ),
                Product2Page3SpecialDestinationRowVM(
                    combination_key="special__laktosfri",
                    label="Laktosfri",
                    quantity=1,
                    dishes=(
                        Product2Page3SpecialDestinationDishVM(option_id="option-2", display_title="Ugnsbakad fisk med dill", quantity=1),
                    ),
                ),
            ),
        ),
        Product2Page3SpecialDestinationGroupVM(
            destination_id="dept-16",
            display_name="Avdelning 16",
            rows=(
                Product2Page3SpecialDestinationRowVM(
                    combination_key="special__glutenfri",
                    label="Glutenfri",
                    quantity=3,
                    dishes=(
                        Product2Page3SpecialDestinationDishVM(option_id="option-2", display_title="Ugnsbakad fisk med dill", quantity=3),
                    ),
                ),
            ),
        ),
    )
    return Product2Page3VM(
        tenant_id=1,
        site_id="site-1",
        site_name="Centralköket E2E",
        service_date="2026-09-08",
        service_date_label="tisdag 8 september 2026",
        service_date_compact_label="tis 8 sep",
        meal="lunch",
        meal_label="Lunch",
        ready=ready,
        ready_label="Underlag granskat" if ready else "Underlag behöver granskas",
        blockers=(() if ready else ("UNREVIEWED_OPTIONS",)),
        blocker_messages=blocker_messages,
        view=view,
        special_view=special_view,
        overview_options=(
            Product2Page3OptionVM(
                option_id="option-1",
                display_label="Alt 1",
                display_title="Vardagsgryta med rotfrukter",
                has_demand=True,
                status_label=None,
                blockers=(),
                baseline_total=79,
                normal_total=79,
                special_total=0,
                normal_department_rows=(
                    Product2Page3DestinationVM(destination_id="dept-01", display_name="Avdelning 01", baseline_quantity=79),
                ),
                special_cohorts=(),
            ),
            Product2Page3OptionVM(
                option_id="option-2",
                display_label="Alt 2",
                display_title="Ugnsbakad fisk med dill",
                has_demand=True,
                status_label=None,
                blockers=(),
                baseline_total=62,
                normal_total=54,
                special_total=8,
                normal_department_rows=(
                    Product2Page3DestinationVM(destination_id="dept-11", display_name="Avdelning 11", baseline_quantity=62),
                ),
                special_cohorts=(
                    Product2Page3SpecialCohortVM(
                        label="Glutenfri",
                        quantity=4,
                        department_quantities=(
                            Product2Page3DepartmentQuantityVM(destination_id="dept-11", display_name="Avdelning 11", quantity=4),
                        ),
                    ),
                ),
            ),
        ),
        normal_matrix=normal_matrix,
        special_production_groups=special_production_groups,
        special_destination_groups=special_destination_groups,
        page1_url="/ui/kitchen/planering?ui=product2&site_id=site-1&year=2026&week=37&day=1",
        page2_url="/ui/kitchen/planering/day?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&option_id=option-1",
        navigation_urls={
            "overview": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=overview",
            "normal": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=normal",
            "special": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=special&special_view=production",
        },
        special_navigation_urls={
            "production": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=special&special_view=production",
            "department": "/ui/kitchen/planering/day/production?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch&view=special&special_view=department",
        },
        publication_identity=object(),
        options=(),
        unassigned_destinations=(),
    )


def test_page3_route_renders_production_underlag(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Site", tenant_id=1)
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: _page3_vm())

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Produktionsunderlag" in html
    assert "PRODUKTIONSUNDERLAG" not in html
    assert "Kommunköket" in html
    assert "Fläskkarré" in html
    assert "Översikt" in html
    assert "Normalkost" in html
    assert "Specialkost" in html
    assert 'data-testid="app-shell"' in html
    assert 'app-shell__nav-item--active" href="/ui/kitchen/planering"' in html
    assert "← Granska anpassningar" in html
    assert "Dagens mål" not in html
    assert 'href="/ui/kitchen/planering/day?ui=product2&amp;site_id=site-1&amp;date=2026-09-08&amp;meal=lunch&amp;option_id=' in html
    assert 'data-theme-toggle' in html
    assert 'class="app-shell__theme-toggle"' in html
    assert 'planera_product2_page3.js' in html
    assert 'style="' not in html
    assert 'data-page3-view-link' in html
    assert 'data-page3-panel="overview"' in html
    assert 'data-page3-stickybar' not in html
    assert 'data-page3-site-id=' in html
    assert 'data-page3-service-date=' in html
    assert 'data-page3-meal=' in html
    assert 'data-page3-year=' in html
    assert 'data-page3-week=' in html
    assert 'href="/ui/kitchen/planering/day?ui=product2&amp;site_id=site-1&amp;date=2026-09-08&amp;meal=lunch&amp;option_id=' in html


def test_page3_route_renders_completion_button_for_ready_targets(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Completion Site", tenant_id=1)
    base_vm = _page3_vm_hierarchy()
    vm = replace(
        base_vm,
        completion_targets=(
            Product2Page3CompletionTargetVM(requirement_group_id="group-a", destination_id="dept-a", service_date="2026-09-08", meal="lunch", quantity=1),
            Product2Page3CompletionTargetVM(requirement_group_id="group-b", destination_id="dept-b", service_date="2026-09-08", meal="lunch", quantity=1),
            Product2Page3CompletionTargetVM(requirement_group_id="group-c", destination_id="dept-a", service_date="2026-09-08", meal="lunch", quantity=2),
        ),
        completion_allowed=True,
    )
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'data-page3-completion-target-departments=\'["dept-a", "dept-b"]\'' in html
    assert 'Markera som tillagad i veckovyn' in html
    assert 'data-page3-completion-button' in html
    assert 'data-page3-special-view-panel="production"' in html
    assert html.index('data-page3-special-view-panel="department"') < html.index('data-page3-completion-shell')
    assert 'data-page3-panel="overview"' in html
    assert html.index('data-page3-completion-shell') > html.index('data-page3-panel="special"')
    special_panel_start = html.index('data-page3-panel="special"')
    assert "hidden" in html[special_panel_start:html.index(">", special_panel_start)]

    normal_rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=normal",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    normal_html = normal_rv.get_data(as_text=True)
    normal_panel_start = normal_html.index('data-page3-panel="special"')
    assert "hidden" in normal_html[normal_panel_start:normal_html.index(">", normal_panel_start)]
    assert normal_html.count('data-page3-completion-button') == 1


def test_page3_route_renders_partial_completion_button_for_unassigned_only(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Completion Blocked Site", tenant_id=1)
    vm = replace(
        _page3_vm_hierarchy(ready=False, blocker_messages=("1 avdelning saknar menyval · underlaget kan ändras.",)),
        completion_allowed=True,
        completion_targets=(
            Product2Page3CompletionTargetVM(requirement_group_id="group-a", destination_id="dept-a", service_date="2026-09-08", meal="lunch", quantity=1),
        ),
    )
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'data-page3-completion-button' in html
    assert 'Markera som tillagad i veckovyn' in html


def test_page3_route_labels_dessert_and_hides_completion_when_ready(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Dessert Site", tenant_id=1)
    vm = replace(
        _page3_vm_hierarchy(),
        meal_label="Dessert",
        target_variant_type="dessert",
        completion_allowed=False,
        completion_targets=(
            Product2Page3CompletionTargetVM(
                requirement_group_id="group-a",
                destination_id="dept-a",
                service_date="2026-09-08",
                meal="lunch",
                quantity=1,
            ),
        ),
    )
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&option_id=dessert-row",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "· Dessert" in html
    assert 'data-page3-completion-button' not in html


def test_page3_route_hides_completion_button_when_no_completion_targets(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Empty Completion Site", tenant_id=1)
    vm = replace(_page3_vm_hierarchy(), completion_targets=())
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'data-page3-completion-button' not in html
    assert 'Markera som tillagad i veckovyn' not in html


def test_page3_ready_status_is_compact_and_rendered_once(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Ready Status Site", tenant_id=1)
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: _page3_vm_hierarchy())

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert html.count('yp-planera-page3-status-pill') == 1
    assert 'yp-planera-page3-status__text' not in html
    assert 'Läge' not in html
    assert 'Underlag granskat' in html
    assert 'data-page3-stickybar' not in html
    assert 'data-page3-tabs' in html
    assert 'data-page3-view-link' in html


def test_page3_route_supports_canonical_view_params(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 View Site", tenant_id=1)
    def _stub_page3_vm(**kwargs):
        vm = _page3_vm()
        return replace(
            vm,
            view=str(kwargs.get("view") or vm.view),
            special_view=str(kwargs.get("special_view") or vm.special_view),
        )

    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", _stub_page3_vm)

    normal = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=normal",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    special = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=department",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert normal.status_code == 200
    assert "Normalkost" in normal.get_data(as_text=True)
    assert "Avdelning A" in normal.get_data(as_text=True)

    assert special.status_code == 200
    assert "Specialkost" in special.get_data(as_text=True)
    assert 'data-page3-special-view="department"' in special.get_data(as_text=True)
    assert 'data-page3-special-view-link' in special.get_data(as_text=True)
    assert "Avdelning A" in special.get_data(as_text=True)
    assert "Produktionslista" in special.get_data(as_text=True)
    assert "Packlista" in special.get_data(as_text=True)


def test_page3_route_preserves_explicit_option_id(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Explicit Option Site", tenant_id=1)
    captured: dict[str, object] = {}

    def _stub_page3_vm(**kwargs):
        captured["meal"] = kwargs.get("meal")
        captured["option_id"] = kwargs.get("option_id")
        return _page3_vm()

    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", _stub_page3_vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=dinner&option_id=opt-dinner",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    assert captured["meal"] == "dinner"
    assert captured["option_id"] == "opt-dinner"


def test_page3_route_renders_primary_bucket_aggregation_in_production_view(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Primary Bucket Site", tenant_id=1)
    vm = replace(
        _page3_vm_hierarchy(view="special", special_view="production"),
        special_production_groups=(
            Product2Page3SpecialProductionGroupVM(
                combination_key="option-a::timbal",
                label="Timbal",
                quantity=6,
                dishes=(
                    Product2Page3SpecialDishVM(
                        option_id="option-a",
                        display_title="Timbal",
                        quantity=3,
                        department_quantities=(
                            Product2Page3DepartmentQuantityVM(destination_id="dept-a", display_name="Avdelning A", quantity=3),
                        ),
                    ),
                    Product2Page3SpecialDishVM(
                        option_id="option-a",
                        display_title="Timbal + Glutenfri",
                        quantity=1,
                        department_quantities=(
                            Product2Page3DepartmentQuantityVM(destination_id="dept-a", display_name="Avdelning A", quantity=1),
                        ),
                    ),
                    Product2Page3SpecialDishVM(
                        option_id="option-a",
                        display_title="Timbal + Laktosfri",
                        quantity=2,
                        department_quantities=(
                            Product2Page3DepartmentQuantityVM(destination_id="dept-a", display_name="Avdelning A", quantity=2),
                        ),
                    ),
                ),
                modifier_labels=("Glutenfri", "Laktosfri"),
                unresolved_primary=False,
            ),
            Product2Page3SpecialProductionGroupVM(
                combination_key="option-d::timbal",
                label="Timbal",
                quantity=5,
                dishes=(
                    Product2Page3SpecialDishVM(
                        option_id="option-d",
                        display_title="Timbal kväll",
                        quantity=5,
                        department_quantities=(
                            Product2Page3DepartmentQuantityVM(destination_id="dept-d", display_name="Avdelning D", quantity=5),
                        ),
                    ),
                ),
                modifier_labels=(),
                unresolved_primary=False,
            ),
        ),
    )
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=production",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert html.count('data-page3-special-group="option-a::timbal"') == 1
    assert "6 portioner" in html
    assert "5 portioner" in html
    assert "Glutenfri" in html
    assert "Laktosfri" in html


def test_page3_route_renders_xor_special_views_for_production_and_department(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Special XOR Site", tenant_id=1)
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **kwargs: _page3_vm_hierarchy(view="special", special_view=str(kwargs.get("special_view") or "production")))

    production = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=production",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    department = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=department",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert production.status_code == 200
    production_html = production.get_data(as_text=True)
    assert 'data-page3-special-view-panel="production"' in production_html
    assert 'data-page3-special-view-panel="department"' in production_html
    assert not _tag_has_hidden(production_html, 'data-page3-special-view-panel="production"')
    assert _tag_has_hidden(production_html, 'data-page3-special-view-panel="department"')

    assert department.status_code == 200
    department_html = department.get_data(as_text=True)
    assert 'data-page3-special-view-panel="production"' in department_html
    assert 'data-page3-special-view-panel="department"' in department_html
    assert _tag_has_hidden(department_html, 'data-page3-special-view-panel="production"')
    assert not _tag_has_hidden(department_html, 'data-page3-special-view-panel="department"')


def test_page3_special_view_renders_exact_combination_without_redundant_pills(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Modifier Site", tenant_id=1)
    base_vm = _page3_vm_hierarchy(view="special", special_view="production")
    custom_vm = replace(
        base_vm,
        special_production_groups=(
            Product2Page3SpecialProductionGroupVM(
                combination_key="special__timbal__glutenfri",
                label="Timbal + Glutenfri",
                quantity=3,
                dishes=(
                    Product2Page3SpecialDishVM(
                        option_id="option-1",
                        display_title="Vardagsgryta med rotfrukter",
                        quantity=3,
                        department_quantities=(
                            Product2Page3DepartmentQuantityVM(destination_id="dept-16", display_name="Avdelning 16", quantity=3),
                        ),
                    ),
                ),
                modifier_labels=("Glutenfri",),
                unresolved_primary=False,
            ),
        ),
        special_destination_groups=(
            Product2Page3SpecialDestinationGroupVM(
                destination_id="dept-16",
                display_name="Avdelning 16",
                rows=(
                    Product2Page3SpecialDestinationRowVM(
                        combination_key="special__timbal__glutenfri",
                        label="Timbal + Glutenfri",
                        quantity=3,
                        dishes=(
                            Product2Page3SpecialDestinationDishVM(
                                option_id="option-1",
                                display_title="Vardagsgryta med rotfrukter",
                                quantity=3,
                            ),
                        ),
                        modifier_labels=("Glutenfri",),
                        unresolved_primary=False,
                    ),
                ),
            ),
        ),
    )
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: custom_vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=production",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert html.count('aria-label="Skriv ut aktuell vy"') == 1
    assert 'aria-label="Skriv ut aktuell vy"' in html
    assert 'title="Skriv ut aktuell vy"' in html
    assert 'static/js/planera_product2_page3.js' in html
    assert "Timbal + Glutenfri" in html
    assert "Glutenfri" in html
    assert "yp-planera-page3-pill--modifier" not in html
    assert "yp-planera-page3-pill--menu" not in html
    assert "Huvudsaklig specialkost behöver anges" not in html


def test_page3_print_title_and_preliminary_warning_follow_active_special_view(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Print Site", tenant_id=1)
    monkeypatch.setattr(
        "core.ui_blueprint.build_product2_page3_vm",
        lambda **_: _page3_vm_hierarchy(
            view="special",
            special_view="department",
            ready=False,
            blocker_messages=("Avdelning saknar val",),
        ),
    )

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=department",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Specialkost – Packlista" in html
    assert "Preliminärt underlag: Avdelning saknar val" in html
    assert html.count('aria-label="Skriv ut aktuell vy"') == 1


def test_page3_route_hides_inactive_panels_for_special_department_view(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 All Panels Site", tenant_id=1)
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: _page3_vm_hierarchy(view="special", special_view="department"))

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=department",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'data-page3-stickybar' not in html
    assert _tag_has_hidden(html, 'data-page3-panel="overview"')
    assert _tag_has_hidden(html, 'data-page3-panel="normal"')
    assert not _tag_has_hidden(html, 'data-page3-panel="special"')
    assert 'data-page3-special-view-link' in html
    assert _tag_has_hidden(html, 'data-page3-special-view-panel="production"')
    assert not _tag_has_hidden(html, 'data-page3-special-view-panel="department"')
    assert 'RÄTT' not in html
    assert 'AVDELNINGAR' not in html
    assert 'Glutenfri' in html
    assert 'Laktosfri' in html
    assert 'Avdelning 16' in html
    assert 'Glutenfri' in html
    assert '4 portioner' in html
    assert 'Laktosfri' in html
    assert '1 portion' in html


def test_page3_route_renders_navigation_and_history_hooks(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Sticky Site", tenant_id=1)
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: _page3_vm_hierarchy(view="overview"))

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=overview",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'data-page3-view-link' in html
    assert 'data-page3-special-view=' in html
    assert 'data-page3-stickybar' not in html


def test_page3_route_renders_compact_normal_headers_and_totals(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Normal Matrix Site", tenant_id=1)
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: _page3_vm_hierarchy(view="normal"))

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=normal",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "79 portioner" not in html
    assert "54 portioner" not in html
    assert "SUMMA" in html
    assert "kända portioner" not in html
    assert "2 rätt" not in html
    assert 'yp-planera-page3-matrix-column-title' in html
    assert 'data-page3-normal-selector' in html
    assert "Alla r" in html
    assert '<option value="" selected>' in html
    assert '<option value="option-1"' in html
    assert '<option value="option-2"' in html


def test_page3_normal_selector_defaults_to_target_option(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Target Normal Site", tenant_id=1)
    vm = replace(_page3_vm_hierarchy(view="normal"), target_option_id="option-2")
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=normal&option_id=option-2",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert '<option value="option-2" selected>Ugnsbakad fisk med dill</option>' in html
    assert '<option value="" selected>Alla rätter</option>' not in html
    assert 'data-page3-all-normal-link' in html
    assert 'meal=lunch&amp;view=normal' in html
    assert '&amp;option_id=' not in html.split('data-page3-all-normal-link', 1)[1].split('</a>', 1)[0]
    assert 'data-page3-normal-single-heading="option-2"' in html


def test_page3_targeted_non_lunch_does_not_offer_full_meal_link(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Target Dinner Site", tenant_id=1)
    vm = replace(_page3_vm_hierarchy(view="normal"), meal="dinner", target_option_id="option-2")
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=dinner&view=normal&option_id=option-2",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "data-page3-all-normal-link" not in html
    assert "data-page3-all-overview-link" not in html


def test_page3_targeted_lunch_overview_offers_full_lunch_link(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Overview Lunch Site", tenant_id=1)
    vm = replace(_page3_vm_hierarchy(view="overview"), target_option_id="option-2")
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: vm)

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=overview&option_id=option-2",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "data-page3-all-overview-link" in html
    assert "Visa hela lunchen" in html
    link = html.split("data-page3-all-overview-link", 1)[1].split("</a>", 1)[0]
    assert "meal=lunch&amp;view=overview" in link
    assert "&amp;option_id=" not in link


def test_page3_normal_selector_is_driven_by_external_state_script():
    script = (Path(__file__).parents[2] / "static" / "js" / "planera_product2_page3.js").read_text(
        encoding="utf-8"
    )
    css = (Path(__file__).parents[2] / "static" / "css" / "planera_product2_page3.css").read_text(
        encoding="utf-8"
    )

    assert "data-page3-normal-selector" in script
    assert "data-page3-normal-option" in script
    assert "applyNormalSelection" in script
    assert 'window.addEventListener("beforeprint"' in script
    assert "showState(readStateFromUrl()" in script
    assert ".yp-planera-page3-normal-single-heading[hidden]" in css
    assert "display: none !important" in css


def test_page3_route_renders_incomplete_blocker_details(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Blocker Site", tenant_id=1)
    monkeypatch.setattr(
        "core.ui_blueprint.build_product2_page3_vm",
        lambda **_: _page3_vm_hierarchy(ready=False, blocker_messages=("Produktion saknar beslut",)),
    )

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Underlag behöver granskas' in html
    assert 'Produktion saknar beslut' in html
    assert 'yp-planera-page3-status__text' not in html


def test_page3_print_styles_keep_overview_and_matrix_text_dark():
    css = (Path(__file__).parents[2] / "static" / "css" / "planera_product2_page3.css").read_text(encoding="utf-8")
    print_css = css[css.index("@media print"):]

    assert ".yp-planera-page3-table th" in print_css
    assert ".yp-planera-page3-table td" in print_css
    assert ".yp-planera-page3-overview-row__title" in print_css
    assert ".yp-planera-page3-matrix-column-title" in print_css
    assert ".yp-planera-page3-matrix-column-total" in print_css
    assert ".yp-planera-page3-table--matrix .is-sticky" in print_css
    assert "color: #071426 !important" in print_css
    assert "background: #fff !important" in print_css
    assert ".yp-planera-page3-date-control__arrow" in print_css
    assert ".yp-planera-page3-action-row" in print_css
    assert ".yp-planera-page3-special-completion" in css


def test_page3_route_hides_empty_special_departments(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Special Filter Site", tenant_id=1)
    monkeypatch.setattr(
        "core.ui_blueprint.build_product2_page3_vm",
        lambda **_: _page3_vm_hierarchy(view="special", special_view="department"),
    )

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=department",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    special_section = html[html.index('data-page3-panel="special"'):]
    assert 'data-page3-special-view="department"' in html
    assert _tag_has_hidden(html, 'data-page3-special-view-panel="production"')
    assert not _tag_has_hidden(html, 'data-page3-special-view-panel="department"')
    assert "Packlista" in special_section
    assert "Avdelning 11" in special_section
    assert "Glutenfri" in special_section
    assert "Laktosfri" in special_section
    assert "Ugnsbakad fisk med dill" in special_section
    assert "RÄTT" not in special_section
    assert "AVDELNINGAR" not in special_section


def test_page3_route_keeps_special_hierarchy_with_multi_dish_cohort(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Special Hierarchy Site", tenant_id=1)
    monkeypatch.setattr(
        "core.ui_blueprint.build_product2_page3_vm",
        lambda **_: _page3_vm_hierarchy(view="special", special_view="production"),
    )

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch&view=special&special_view=production",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    production_panel = html[html.index('data-page3-panel="special"'):]
    assert 'data-page3-special-view-panel="production"' in production_panel
    assert "RÄTT" not in production_panel
    assert "AVDELNINGAR" not in production_panel
    assert "Avdelning 16" in production_panel
    assert "2 portioner" in production_panel
    assert "Glutenfri" in production_panel
    assert "Timbal" in production_panel
    assert "Vardagsgryta med rotfrukter" in production_panel
    assert "Ugnsbakad fisk med dill" in production_panel
    assert "Avdelning 01" in production_panel
    assert "Avdelning 16" in production_panel


def test_page3_route_allows_kitchen_role_and_fails_cross_tenant(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site_1, _ = SitesRepo().create_site(name="Page3 Security Site A", tenant_id=1)
    db = get_session()
    try:
        db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(2, 'Tenant 2', 1)"))
        db.commit()
    finally:
        db.close()
    site_2, _ = SitesRepo().create_site(name="Page3 Security Site B", tenant_id=2)
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: _page3_vm())

    allowed = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site_1['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "kitchen", "X-Tenant-Id": "1"},
    )
    blocked = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site_2['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "kitchen", "X-Tenant-Id": "1"},
    )

    assert allowed.status_code == 200
    assert blocked.status_code == 404


def test_page3_route_rejects_invalid_parameters_without_leaking_data(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Invalid Params Site", tenant_id=1)
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: _page3_vm())

    bad_site = client.get("/ui/kitchen/planering/day/production?ui=product2&date=2026-09-08&meal=lunch", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    bad_date = client.get(f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&meal=lunch", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    bad_meal = client.get(f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=dinner", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})

    assert bad_site.status_code == 404
    assert bad_date.status_code == 404
    assert bad_meal.status_code == 404


def test_page3_route_hides_service_addons_from_output(app_session, monkeypatch):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1

    site, _ = SitesRepo().create_site(name="Page3 Addon Site", tenant_id=1)
    department, _ = DepartmentsRepo().create_department(site_id=site["id"], name="Avdelning Addon", resident_count_mode="fixed", resident_count_fixed=12)
    addon_repo = ServiceAddonsRepo()
    mos_id = addon_repo.create_if_missing("Mos", site_id=site["id"], addon_family="mos")
    sallad_id = addon_repo.create_if_missing("Sallad", site_id=site["id"], addon_family="sallad")
    DepartmentServiceAddonsRepo().replace_for_department(
        department["id"],
        [
            {"addon_id": mos_id, "lunch_count": 3, "dinner_count": 0, "note": ""},
            {"addon_id": sallad_id, "lunch_count": 0, "dinner_count": 2, "note": ""},
        ],
        site_id=site["id"],
    )
    monkeypatch.setattr("core.ui_blueprint.build_product2_page3_vm", lambda **_: _page3_vm())

    rv = client.get(
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={site['id']}&date=2026-09-08&meal=lunch",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Mos" not in html
    assert "Sallad" not in html