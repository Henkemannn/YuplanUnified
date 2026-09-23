from __future__ import annotations

from core.admin_repo import DepartmentServiceAddonsRepo, DepartmentsRepo, ServiceAddonsRepo, SitesRepo
from core.db import get_session
from sqlalchemy import text
from core.planera_product2_page3_vm import (
    Product2Page3DestinationVM,
    Product2Page3OptionVM,
    Product2Page3SpecialCohortVM,
    Product2Page3VM,
)


def _page3_vm() -> Product2Page3VM:
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
        page2_url="/ui/kitchen/planering/day?ui=product2&site_id=site-1&date=2026-09-08&meal=lunch",
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
    assert "Normalkost" in html
    assert "Specialkost" in html
    assert "Tillbaka till granskning" in html


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