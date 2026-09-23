from __future__ import annotations

from dataclasses import replace
import re

from core.admin_repo import DepartmentServiceAddonsRepo, DepartmentsRepo, ServiceAddonsRepo, SitesRepo
from core.db import get_session
from sqlalchemy import text
from core.planera_product2_page3_vm import (
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
        page2_url="/ui/kitchen/planering/day?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch",
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
        page2_url="/ui/kitchen/planering/day?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch",
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
    assert "PRODUKTIONSUNDERLAG" in html
    assert "Kommunköket" in html
    assert "Fläskkarré" in html
    assert "Översikt" in html
    assert "Normalkost" in html
    assert "Specialkost" in html
    assert "Granska underlag" in html
    assert 'data-theme-toggle' in html
    assert 'id="ypProductThemeToggle"' in html
    assert 'kitchen_product_shell.js' in html
    assert 'planera_product2_page3.js' in html
    assert 'style="' not in html
    assert 'data-page3-view-link' in html
    assert 'data-page3-panel="overview"' in html
    assert 'data-page3-stickybar' not in html


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
    assert "Avdelning A" in special.get_data(as_text=True)


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
    assert 'data-page3-special-group' in html
    assert 'Avdelning 11' in html


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
    assert "79 portioner" in html
    assert "54 portioner" in html
    assert "TOTALT" in html
    assert "2 rätt" not in html
    assert 'yp-planera-page3-matrix-column-total' in html
    assert 'yp-planera-page3-matrix-column-title' in html


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
    assert "Specialkost" in special_section
    assert "Glutenfri" in special_section
    assert "Timbal" in special_section


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
    assert production_panel.index("Glutenfri") < production_panel.index("Ugnsbakad fisk med dill")
    assert production_panel.index("Timbal") < production_panel.index("Vardagsgryta med rotfrukter") < production_panel.index("Avdelning 01")
    timbal_html = production_panel[production_panel.index("Timbal"):]
    assert timbal_html.index("Vardagsgryta med rotfrukter") < timbal_html.index("Avdelning 01")
    assert timbal_html.index("Ugnsbakad fisk med dill") < timbal_html.index("Avdelning 16")


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