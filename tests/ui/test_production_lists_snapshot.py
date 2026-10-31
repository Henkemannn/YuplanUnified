from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import text

from core.admin_repo import (
    DepartmentServiceAddonsRepo,
    ServiceAddonsRepo,
    SitesRepo,
)
from core.db import get_session
from core.production_lists_repo import ProductionListsRepo


def _h(role: str = "admin") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _set_active_site(client, site_id: str) -> None:
    with client.session_transaction() as sess:
        sess["site_id"] = site_id


def test_create_production_list_snapshot(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    payload = {
        "site_id": site["id"],
        "date": "2026-02-10",
        "meal_type": "lunch",
        "payload": {
            "year": 2026,
            "week": 7,
            "day_label": "Tis",
            "meal_label": "Lunch",
            "normal": {"rows": [], "alt1_total": 0, "alt2_total": 0, "total": 0},
            "special": {"worklist": []},
        },
    }
    resp = client_admin.post("/api/production-lists", headers=_h(), json=payload)
    assert resp.status_code == 201
    body = resp.get_json() or {}
    assert body.get("ok") is True
    assert (body.get("item") or {}).get("id")


def test_production_list_renders(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list render site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    item = ProductionListsRepo().create_snapshot(
        site_id=site["id"],
        date_iso="2026-02-11",
        meal_type="lunch",
        payload={
            "week": 7,
            "day_label": "Ons",
            "meal": "lunch",
            "meal_label": "Lunch",
            "dishes": {"alt1": "Pasta", "alt2": "Fisk"},
            "normal": {
                "rows": [
                    {"department_name": "Avd A", "alt_choice": "alt1", "count": 4},
                    {"department_name": "Avd B", "alt_choice": "alt2", "count": 2},
                ],
                "alt1_total": 4,
                "alt2_total": 2,
            },
            "special": {
                "worklist": [
                    {
                        "diet_type_name": "Glutenfri",
                        "total": 2,
                        "rows": [{"department_name": "Avd A", "count": 2, "alt_label": "Alt1"}],
                    }
                ]
            },
            "service_addon": {
                "addon_name": "Mos",
                "total_count": 3,
                "departments": [{"department_name": "Avd A", "count": 3, "note": "Extra"}],
            },
        },
    )

    rv = client_admin.get(f"/ui/production-lists/{item['id']}?site_id={site['id']}", headers=_h())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Tillagningslista" in html
    assert "Glutenfri" in html
    assert "Serveringstillägg" in html
    assert 'id="snapshot-print-root" class="snapshot-screen-root"' in html
    assert 'id="snapshot-print-root" class="kp-print"' not in html


def test_save_api_creates_row_and_detail_not_empty(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list api save site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    payload = {
        "site_id": site["id"],
        "date": "2026-02-14",
        "meal_type": "lunch",
        "payload": {
            "week": 7,
            "day_label": "Lör",
            "meal": "lunch",
            "meal_label": "Lunch",
            "dishes": {"alt1": "Pasta", "alt2": "Fisk"},
            "normal": {"rows": [{"department_name": "Avd A", "alt_choice": "alt1", "count": 3}], "alt1_total": 3, "alt2_total": 0, "total": 3},
            "special": {"worklist": [{"diet_type_name": "Glutenfri", "total": 1, "rows": [{"department_name": "Avd A", "count": 1, "alt_label": "Alt1"}]}]},
        },
    }
    save = client_admin.post("/api/production-lists", headers=_h(), json=payload)
    assert save.status_code == 201
    body = save.get_json() or {}
    item_id = (body.get("item") or {}).get("id")
    assert item_id

    listed = ProductionListsRepo().list_for_site(site["id"])
    assert any(str(it.get("id")) == str(item_id) for it in listed)

    detail = client_admin.get(f"/ui/production-lists/{item_id}?site_id={site['id']}", headers=_h())
    assert detail.status_code == 200
    html = detail.get_data(as_text=True)
    assert "Tillagningslista" in html
    assert "Glutenfri" in html
    assert 'id="snapshot-print-root" class="snapshot-screen-root"' in html


def test_production_lists_index_renders_and_keeps_site_id(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list index site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    rv = client_admin.get(f"/ui/production-lists?site_id={site['id']}", headers=_h())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Produktionslistor" in html
    assert f"/ui/production-lists?site_id={site['id']}" in html


def test_production_lists_index_renders_selected_iso_week_and_lunch_links(app_session, client_admin, monkeypatch):
    site, _ = SitesRepo().create_site(f"Prod list week site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])
    monkeypatch.setattr(
        "core.ui_blueprint.build_product2_page2_planning_context",
        lambda **_: SimpleNamespace(status="ok", options=(object(),)),
    )

    rv = client_admin.get(
        f"/ui/production-lists?site_id={site['id']}&year=2026&week=1",
        headers=_h(),
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Vecka 1" in html
    assert html.count('class="production-lists-day-row"') == 7
    assert html.count("meal=lunch") == 14
    assert "view=overview" in html
    assert "option_id" not in html
    assert "year=2025&amp;week=52" in html
    assert "year=2026&amp;week=2" in html
    assert "2025" in html
    assert "29 december" in html
    assert "Måndag" in html
    assert "Tisdag" in html
    assert "Onsdag" in html
    assert "Torsdag" in html
    assert "Fredag" in html
    assert "Lördag" in html
    assert "Söndag" in html
    assert 'name="week"' in html
    assert 'name="year"' in html
    assert "production-lists-week-submit" not in html
    assert "production-lists-service-link" in html
    assert "yp-button-primary" not in html


def test_production_lists_index_supports_week_53_and_selected_picker_values(app_session, client_admin, monkeypatch):
    site, _ = SitesRepo().create_site(f"Prod list week 53 site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])
    monkeypatch.setattr(
        "core.ui_blueprint.build_product2_page2_planning_context",
        lambda **_: SimpleNamespace(status="no_publication", options=()),
    )

    rv = client_admin.get(
        f"/ui/production-lists?site_id={site['id']}&year=2026&week=53",
        headers=_h(),
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert '<option value="53" selected>Vecka 53</option>' in html
    assert '<option value="2026" selected>2026</option>' in html


def test_production_lists_week_picker_navigates_without_submit_button():
    script = (Path(__file__).parents[2] / "static" / "js" / "production_lists.js").read_text(encoding="utf-8")
    css = (Path(__file__).parents[2] / "static" / "css" / "production_lists.css").read_text(encoding="utf-8")
    addons_script = (Path(__file__).parents[2] / "static" / "js" / "production_lists_addons.js").read_text(encoding="utf-8")

    assert 'weekSelect.addEventListener("change", navigate)' in script
    assert 'yearSelect.addEventListener("change", navigate)' in script
    assert "form.submit()" in script
    assert "color: var(--text)" in css
    assert "background-color: var(--surface-2)" in css
    assert "color-scheme: light dark" in css
    assert ".production-lists-day-row > .production-lists-services" in css
    assert "production-lists-addon-toggle" not in script
    assert "window.print()" in addons_script
    assert "afterprint" in addons_script
    assert "data-production-lists-print-family" in addons_script
    assert "data-production-lists-print-all" in addons_script
    assert "@media print" in css
    assert "break-inside: avoid" in css


def test_production_lists_index_defaults_to_current_iso_week(app_session, client_admin, monkeypatch):
    site, _ = SitesRepo().create_site(f"Prod list current week site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 12, 31)

    monkeypatch.setattr("core.ui_blueprint._date", FrozenDate)
    monkeypatch.setattr(
        "core.ui_blueprint.build_product2_page2_planning_context",
        lambda **_: SimpleNamespace(status="no_publication", options=()),
    )

    rv = client_admin.get(f"/ui/production-lists?site_id={site['id']}", headers=_h())

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Vecka 53" in html
    assert "2026" in html
    assert "Ej publicerad" in html


def test_production_lists_index_rejects_site_outside_tenant(app_session, client_admin):
    with app_session.app_context():
        db = get_session()
        db.execute(
            text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(2, 'Other tenant', 1)")
        )
        db.commit()
        db.close()
        foreign_site, _ = SitesRepo().create_site(
            f"Prod list foreign site {uuid.uuid4()}",
            tenant_id=2,
        )
    _set_active_site(client_admin, foreign_site["id"])

    rv = client_admin.get(
        f"/ui/production-lists?site_id={foreign_site['id']}",
        headers=_h(),
    )

    assert rv.status_code == 404
    addons = client_admin.get(
        f"/ui/production-lists/addons?site_id={foreign_site['id']}&date=2026-01-05&meal=lunch",
        headers=_h("cook"),
    )
    assert addons.status_code == 404


def test_production_lists_addons_rejects_invalid_date_and_renders_empty_state(
    app_session,
    client_admin,
):
    site, _ = SitesRepo().create_site(f"Prod list empty addon site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    invalid = client_admin.get(
        f"/ui/production-lists/addons?site_id={site['id']}&date=not-a-date&meal=lunch",
        headers=_h("cook"),
    )
    assert invalid.status_code == 404

    empty = client_admin.get(
        f"/ui/production-lists/addons?site_id={site['id']}&date=2026-01-05&meal=lunch",
        headers=_h("cook"),
    )
    assert empty.status_code == 200
    assert "Inga registrerade serveringstillägg" in empty.get_data(as_text=True)


def test_production_lists_requires_active_site_for_index_and_addons(
    app_session,
    client_admin,
):
    site_a, _ = SitesRepo().create_site(f"Prod list active site {uuid.uuid4()}")
    site_b, _ = SitesRepo().create_site(f"Prod list other site {uuid.uuid4()}")

    with client_admin.session_transaction() as sess:
        sess.pop("site_id", None)
    no_active_index = client_admin.get(
        f"/ui/production-lists?site_id={site_a['id']}",
        headers=_h("cook"),
    )
    no_active_addons = client_admin.get(
        f"/ui/production-lists/addons?site_id={site_a['id']}&date=2026-01-05&meal=lunch",
        headers=_h("cook"),
    )
    assert no_active_index.status_code == 302
    assert no_active_addons.status_code == 302
    assert "/ui/select-site" in no_active_index.headers["Location"]
    assert "/ui/select-site" in no_active_addons.headers["Location"]

    _set_active_site(client_admin, site_a["id"])
    other_index = client_admin.get(
        f"/ui/production-lists?site_id={site_b['id']}",
        headers=_h("cook"),
    )
    other_addons = client_admin.get(
        f"/ui/production-lists/addons?site_id={site_b['id']}&date=2026-01-05&meal=lunch",
        headers=_h("cook"),
    )
    assert other_index.status_code == 404
    assert other_addons.status_code == 404

    own_index = client_admin.get(
        f"/ui/production-lists?site_id={site_a['id']}",
        headers=_h("cook"),
    )
    own_addons = client_admin.get(
        f"/ui/production-lists/addons?site_id={site_a['id']}&date=2026-01-05&meal=lunch",
        headers=_h("cook"),
    )
    assert own_index.status_code == 200
    assert own_addons.status_code == 200


def test_production_lists_index_renders_lunch_service_addons_without_new_requests(
    app_session,
    client_admin,
    monkeypatch,
):
    site, _ = SitesRepo().create_site(f"Prod list addon site {uuid.uuid4()}")
    department_id = f"prod-addon-department-{uuid.uuid4()}"
    with app_session.app_context():
        db = get_session()
        db.execute(
            text(
                """
                INSERT INTO departments(
                    id, site_id, name, resident_count_mode, resident_count_fixed, version
                ) VALUES(:id, :site_id, :name, 'fixed', 10, 0)
                """
            ),
            {
                "id": department_id,
                "site_id": site["id"],
                "name": "Avdelning 11",
            },
        )
        db.commit()
        db.close()

    addon_repo = ServiceAddonsRepo()
    mos_id = addon_repo.create_if_missing(
        "Mos",
        site_id=site["id"],
        addon_family="mos",
    )
    salad_id = addon_repo.create_if_missing(
        "Sallad",
        site_id=site["id"],
        addon_family="sallad",
    )
    dinner_id = addon_repo.create_if_missing(
        "Kvällstillägg",
        site_id=site["id"],
        addon_family="ovrigt",
    )
    inactive_id = addon_repo.create_if_missing(
        "Inaktivt tillägg",
        site_id=site["id"],
        addon_family="ovrigt",
    )
    addon_rows = DepartmentServiceAddonsRepo()
    addon_rows.add_for_department(
        department_id,
        mos_id,
        service_scope="lunch",
        quantity_mode="custom",
        lunch_count=4,
        dinner_count=None,
        note="Aldrig tomat",
        site_id=site["id"],
    )
    addon_rows.add_for_department(
        department_id,
        salad_id,
        service_scope="all_services",
        quantity_mode="whole_department",
        lunch_count=None,
        dinner_count=None,
        note="",
        site_id=site["id"],
    )
    addon_rows.add_for_department(
        department_id,
        dinner_id,
        service_scope="dinner",
        quantity_mode="custom",
        lunch_count=None,
        dinner_count=3,
        note="Kväll endast",
        site_id=site["id"],
    )
    addon_rows.add_for_department(
        department_id,
        inactive_id,
        service_scope="lunch",
        quantity_mode="custom",
        lunch_count=8,
        dinner_count=None,
        note="Ska inte visas",
        site_id=site["id"],
    )
    with app_session.app_context():
        db = get_session()
        db.execute(
            text("UPDATE service_addons SET is_active=0 WHERE id=:id"),
            {"id": inactive_id},
        )
        db.commit()
        db.close()

    _set_active_site(client_admin, site["id"])
    monkeypatch.setattr(
        "core.ui_blueprint.build_product2_page2_planning_context",
        lambda **_: SimpleNamespace(status="ok", options=(object(),)),
    )

    rv = client_admin.get(
        f"/ui/production-lists?site_id={site['id']}&year=2026&week=1",
        headers=_h("cook"),
    )

    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert html.count('class="production-lists-addon-link"') == 7
    assert "production-lists-addon-toggle" not in html
    assert "production-lists-addon-panel" not in html
    assert "ui/production-lists/addons" in html
    assert "2025-12-29" in html
    assert "meal=lunch" in html
    assert "view=overview" in html

    addons = client_admin.get(
        f"/ui/production-lists/addons?site_id={site['id']}&date=2026-01-05&meal=lunch&year=2026&week=1",
        headers=_h("cook"),
    )
    assert addons.status_code == 200
    addons_html = addons.get_data(as_text=True)
    assert "Serveringstillägg" in addons_html
    assert "5 januari 2026 · Lunch" in addons_html
    assert "Tillbaka till Produktionslistor" in addons_html
    assert "Mos" in addons_html
    assert "Avdelning 11" in addons_html
    assert "4" in addons_html
    assert "Aldrig tomat" in addons_html
    assert "Sallad" in addons_html
    assert "10" in addons_html
    assert ">mos<" in addons_html
    assert ">sallad<" in addons_html
    assert "Kvällstillägg" not in addons_html
    assert "Inaktivt tillägg" not in addons_html
    assert "Ska inte visas" not in addons_html
    assert "stå" in addons_html
    assert "year=2026&amp;week=1" in addons_html
    assert 'aria-label="Skriv ut alla serveringstillägg"' in addons_html
    assert addons_html.count("data-production-lists-print-family") == 2
    assert "data-production-lists-print-all" in addons_html
    assert "production_lists_addons.js" in addons_html


def test_production_list_shows_production_group_with_subtypes_and_departments(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list grouped site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    item = ProductionListsRepo().create_snapshot(
        site_id=site["id"],
        date_iso="2026-02-13",
        meal_type="lunch",
        payload={
            "week": 7,
            "day_label": "Fre",
            "meal": "lunch",
            "meal_label": "Lunch",
            "dishes": {"alt1": "Köttfärssås", "alt2": "Fisk"},
            "normal": {
                "rows": [
                    {"department_name": "Lindgården A", "alt_choice": "alt1", "count": 12},
                ],
                "alt1_total": 12,
                "alt2_total": 0,
            },
            "special": {
                "worklist": [
                    {
                        "diet_type_id": "production:timbal",
                        "production_group_name": "Timbal",
                        "diet_type_name": "Timbal totalt",
                        "total": 12,
                        "subtype_breakdown": [
                            {"diet_type_id": "101", "diet_type_name": "Timbal", "count": 11},
                            {"diet_type_id": "102", "diet_type_name": "Timbal-Fisk", "count": 1},
                        ],
                        "department_breakdown": [
                            {
                                "department_id": "dep-1",
                                "department_name": "Lindgården A",
                                "total": 2,
                                "alt_label": "Alt1",
                                "subtype_counts": [
                                    {"diet_type_name": "Timbal", "count": 2},
                                ],
                            },
                            {
                                "department_id": "dep-2",
                                "department_name": "Boende A",
                                "total": 1,
                                "alt_label": "Alt1",
                                "subtype_counts": [
                                    {"diet_type_name": "Timbal-Fisk", "count": 1},
                                ],
                            },
                        ],
                        "rows": [
                            {"department_name": "Lindgården A", "count": 2, "alt_label": "Alt1"},
                            {"department_name": "Boende A", "count": 1, "alt_label": "Alt1"},
                        ],
                    }
                ]
            },
        },
    )

    rv = client_admin.get(f"/ui/production-lists/{item['id']}?site_id={site['id']}", headers=_h())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Timbal — Totalt 12" in html
    assert "Timbal 11" not in html
    assert "Timbal-Fisk 1" in html
    assert "Till avdelningar" in html
    assert "Lindgården A" in html
    assert "Boende A" in html
    assert html.count("Boende A") == 1
    assert "kp-print-variant-line" in html
    assert "kp-print-subheading" in html
    assert "kp-print-row-subtypes" in html
    assert "Timbal: 2" not in html
    assert "(Timbal-Fisk)" in html
    assert "Textur totalt" not in html


def test_old_lists_cleanup(app_session):
    site, _ = SitesRepo().create_site(f"Prod list cleanup site {uuid.uuid4()}")
    repo = ProductionListsRepo()

    fresh = repo.create_snapshot(
        site_id=site["id"],
        date_iso="2026-02-12",
        meal_type="dinner",
        payload={"meal": "dinner"},
    )

    db = get_session()
    try:
        db.execute(
            text(
                """
                INSERT INTO production_lists(id, site_id, created_at, date, meal_type, payload_json)
                VALUES(:id, :site_id, :created_at, :date, :meal_type, :payload_json)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "site_id": site["id"],
                "created_at": (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S"),
                "date": "2026-01-01",
                "meal_type": "lunch",
                "payload_json": "{}",
            },
        )
        db.commit()
    finally:
        db.close()

    items = repo.list_for_site(site["id"])
    ids = {it["id"] for it in items}
    assert fresh["id"] in ids
    assert len(items) == 1


def test_production_detail_mode_normal_hides_special_section(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list mode normal {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    item = ProductionListsRepo().create_snapshot(
        site_id=site["id"],
        date_iso="2026-02-15",
        meal_type="lunch",
        payload={
            "mode": "normal",
            "week": 7,
            "day_label": "Sön",
            "meal": "lunch",
            "meal_label": "Lunch",
            "dishes": {"alt1": "Pasta", "alt2": "Fisk"},
            "normal": {"rows": [{"department_name": "Avd A", "alt_choice": "alt1", "count": 3}], "alt1_total": 3, "alt2_total": 0},
            "special": {"worklist": [{"diet_type_name": "Glutenfri", "total": 1, "rows": [{"department_name": "Avd A", "count": 1, "alt_label": "Alt1"}]}]},
        },
    )

    rv = client_admin.get(f"/ui/production-lists/{item['id']}?site_id={site['id']}", headers=_h())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Normalkost" in html
    assert "Specialkost" not in html
    assert "Glutenfri" not in html


def test_production_detail_mode_special_hides_normal_section(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list mode special {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    item = ProductionListsRepo().create_snapshot(
        site_id=site["id"],
        date_iso="2026-02-16",
        meal_type="lunch",
        payload={
            "mode": "special",
            "week": 8,
            "day_label": "Mån",
            "meal": "lunch",
            "meal_label": "Lunch",
            "dishes": {"alt1": "Pasta", "alt2": "Fisk"},
            "normal": {"rows": [{"department_name": "Avd A", "alt_choice": "alt1", "count": 3}], "alt1_total": 3, "alt2_total": 0},
            "special": {"worklist": [{"diet_type_name": "Glutenfri", "total": 1, "rows": [{"department_name": "Avd A", "count": 1, "alt_label": "Alt1"}]}]},
        },
    )

    rv = client_admin.get(f"/ui/production-lists/{item['id']}?site_id={site['id']}", headers=_h())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Specialkost" in html
    assert "Glutenfri" in html
    assert "Normalkost" not in html
