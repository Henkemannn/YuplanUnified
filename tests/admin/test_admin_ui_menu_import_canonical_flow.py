from __future__ import annotations

import csv
import io
import json

import pytest
from sqlalchemy import text

from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentAliasRepository,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from core.commun_builder_projection import get_shadow_projection_reader
from core.db import get_session
from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport
from core.menu import MenuService, InMemoryCompositionAliasRepository
from portal.department.auth import DepartmentPortalScope
from portal.department.service import build_department_week_payload

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
TENANT_ID = 1
SITE_ID = "kommuntesta"
DEPARTMENT_ID = "a724a63d-8e3d-4d27-b3bf-1bda637c6087"
YEAR = 2026
WEEK = 35


@pytest.fixture
def client_admin(app_session):
    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = SITE_ID
    return client


def _seed_scope_rows() -> None:
    db = get_session()
    try:
        db.execute(text("DELETE FROM menu_variants WHERE menu_id IN (SELECT id FROM menus WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week)"), {"tid": TENANT_ID, "sid": SITE_ID, "year": YEAR, "week": WEEK})
        db.execute(text("DELETE FROM menus WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"), {"tid": TENANT_ID, "sid": SITE_ID, "year": YEAR, "week": WEEK})
        db.execute(text("DELETE FROM dishes WHERE tenant_id=:tid"), {"tid": TENANT_ID})
        db.execute(text("DELETE FROM commun_builder_menu_links WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"), {"tid": TENANT_ID, "sid": SITE_ID, "year": YEAR, "week": WEEK})
        db.execute(text("DELETE FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"), {"tid": TENANT_ID, "sid": SITE_ID, "year": YEAR, "week": WEEK})
        db.execute(text("DELETE FROM departments WHERE site_id=:sid"), {"sid": SITE_ID})
        db.execute(text("DELETE FROM departments WHERE id=:id"), {"id": DEPARTMENT_ID})
        db.execute(text("INSERT OR REPLACE INTO tenants (id, name, active) VALUES (:id, :name, 1)"), {"id": TENANT_ID, "name": "Primary"})
        db.execute(
            text("INSERT OR REPLACE INTO sites (id, name, tenant_id, version) VALUES (:id, :name, :tid, 0)"),
            {"id": SITE_ID, "name": "KommunTestA", "tid": TENANT_ID},
        )
        db.execute(
            text(
                "INSERT INTO departments (id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) "
                "VALUES (:id, :sid, :name, :mode, :fixed, :notes, 0)"
            ),
            {
                "id": DEPARTMENT_ID,
                "sid": SITE_ID,
                "name": "Avdelning A",
                "mode": "fixed",
                "fixed": 10,
                "notes": "kanon avdelning",
            },
        )
        db.commit()
    finally:
        db.close()


def _build_builder_context(app_session) -> BuilderMenuContextFlow:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    builder_flow = BuilderFlow(
        component_service=ComponentService(repository=component_repository),
        composition_service=CompositionService(repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        component_alias_repository=InMemoryComponentAliasRepository(),
    )
    menu_context_flow = BuilderMenuContextFlow(
        menu_service=MenuService(composition_repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )

    app_session.extensions["builder_menu_context_flow"] = menu_context_flow
    app_session.extensions["builder_flow"] = builder_flow
    return menu_context_flow


def _seed_builder_menu_for_kommun(app_session) -> str:
    with app_session.app_context():
        flow = _build_builder_context(app_session)
        composition_service = CompositionService(repository=flow._composition_repository)

        monday_rows = {
            "comp_monday_alt1": "Köttbullar med gräddsås och potatis",
            "comp_monday_alt2": "Ugnsbakad lax med dillsås och potatis",
            "comp_monday_dessert": "Äppelpaj med vaniljsås",
            "comp_monday_dinner": "Tomatsoppa med ostsmörgås",
        }
        for composition_id, composition_name in monday_rows.items():
            composition_service.create_composition(
                composition_id=composition_id,
                composition_name=composition_name,
            )

        items = [
            ImportedMenuItem(day="monday", meal="lunch", variant_type="alt1", dish_name=monday_rows["comp_monday_alt1"]),
            ImportedMenuItem(day="monday", meal="lunch", variant_type="alt2", dish_name=monday_rows["comp_monday_alt2"]),
            ImportedMenuItem(day="monday", meal="lunch", variant_type="dessert", dish_name=monday_rows["comp_monday_dessert"]),
            ImportedMenuItem(day="monday", meal="kväll", variant_type="kvall", dish_name=monday_rows["comp_monday_dinner"]),
        ]

        weekday_prefixes = [
            "tisdag",
            "onsdag",
            "torsdag",
            "fredag",
            "lördag",
            "söndag",
        ]
        for weekday in weekday_prefixes:
            items.extend(
                [
                    ImportedMenuItem(day=weekday, meal="lunch", variant_type="alt1", dish_name=f"{weekday.title()} okänd rätt alt1"),
                    ImportedMenuItem(day=weekday, meal="lunch", variant_type="alt2", dish_name=f"{weekday.title()} okänd rätt alt2"),
                    ImportedMenuItem(day=weekday, meal="lunch", variant_type="dessert", dish_name=f"{weekday.title()} okänd dessert"),
                    ImportedMenuItem(day=weekday, meal="kväll", variant_type="kvall", dish_name=f"{weekday.title()} kvällsrätt"),
                ]
            )

        from core.commun_builder_import import import_menu_result_to_builder_canonical

        outcome = import_menu_result_to_builder_canonical(
            MenuImportResult(weeks=[WeekImport(year=YEAR, week=WEEK, items=items)]),
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
        )[0]
        return outcome.menu_id


def _kommun_w35_csv_bytes() -> bytes:
    rows: list[dict[str, str]] = [
        {"Year": str(YEAR), "Week": str(WEEK), "Weekday": "Måndag", "Meal": "Lunch", "Alt": "Alt1", "Text": "Köttbullar med gräddsås och potatis"},
        {"Year": str(YEAR), "Week": str(WEEK), "Weekday": "Måndag", "Meal": "Lunch", "Alt": "Alt2", "Text": "Ugnsbakad lax med dillsås och potatis"},
        {"Year": str(YEAR), "Week": str(WEEK), "Weekday": "Måndag", "Meal": "Lunch", "Alt": "Dessert", "Text": "Äppelpaj med vaniljsås"},
        {"Year": str(YEAR), "Week": str(WEEK), "Weekday": "Måndag", "Meal": "Kvällsmat", "Alt": "", "Text": "Tomatsoppa med ostsmörgås"},
    ]

    for weekday, prefix in [
        ("Tisdag", "Tisdag"),
        ("Onsdag", "Onsdag"),
        ("Torsdag", "Torsdag"),
        ("Fredag", "Fredag"),
        ("Lördag", "Lördag"),
        ("Söndag", "Söndag"),
    ]:
        rows.extend(
            [
                {"Year": str(YEAR), "Week": str(WEEK), "Weekday": weekday, "Meal": "Lunch", "Alt": "Alt1", "Text": f"{prefix} okänd rätt alt1"},
                {"Year": str(YEAR), "Week": str(WEEK), "Weekday": weekday, "Meal": "Lunch", "Alt": "Alt2", "Text": f"{prefix} okänd rätt alt2"},
                {"Year": str(YEAR), "Week": str(WEEK), "Weekday": weekday, "Meal": "Lunch", "Alt": "Dessert", "Text": f"{prefix} okänd dessert"},
                {"Year": str(YEAR), "Week": str(WEEK), "Weekday": weekday, "Meal": "Kvällsmat", "Alt": "", "Text": f"{prefix} kvällsrätt"},
            ]
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["Year", "Week", "Weekday", "Meal", "Alt", "Text"])
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def test_admin_menu_import_upload_creates_builder_link_publication_and_portal_payload(app_session, client_admin):
    _seed_scope_rows()
    builder_menu_id = _seed_builder_menu_for_kommun(app_session)

    upload_response = client_admin.post(
        "/ui/admin/menu-import/upload",
        data={"menu_file": (io.BytesIO(_kommun_w35_csv_bytes()), "kommun_w35.csv")},
        content_type="multipart/form-data",
        headers=ADMIN_HEADERS,
        follow_redirects=True,
    )
    assert upload_response.status_code == 200

    db = get_session()
    try:
        legacy_menu = db.execute(
            text("SELECT id, tenant_id, site_id, year, week, status FROM menus WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": TENANT_ID, "sid": SITE_ID, "year": YEAR, "week": WEEK},
        ).fetchone()
        assert legacy_menu is not None
        assert int(legacy_menu[1]) == TENANT_ID
        assert str(legacy_menu[2]) == SITE_ID
        assert int(legacy_menu[3]) == YEAR
        assert int(legacy_menu[4]) == WEEK
        assert str(legacy_menu[5]) == "draft"

        variant_count = db.execute(
            text("SELECT COUNT(*) FROM menu_variants WHERE menu_id=:mid"),
            {"mid": int(legacy_menu[0])},
        ).fetchone()[0]
        assert int(variant_count) == 28

        link = db.execute(
            text("SELECT builder_menu_id, builder_menu_version, source, legacy_menu_id FROM commun_builder_menu_links WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": TENANT_ID, "sid": SITE_ID, "year": YEAR, "week": WEEK},
        ).fetchone()
        assert link is not None
        assert str(link[0]) == builder_menu_id
        assert int(link[1]) == 2
        assert str(link[2]) == "import"
        assert int(link[3]) == int(legacy_menu[0])
    finally:
        db.close()

    rows = app_session.extensions["builder_menu_context_flow"].list_menu_rows(builder_menu_id)
    assert len(rows) == 28
    by_key = {(str(row["day"]), str(row["meal_slot"])): row for row in rows}
    assert by_key[("monday", "lunch_alt1")]["composition_name"] == "Köttbullar med gräddsås och potatis"
    assert by_key[("monday", "lunch_alt2")]["composition_name"] == "Ugnsbakad lax med dillsås och potatis"
    assert by_key[("monday", "lunch_dessert")]["composition_name"] == "Äppelpaj med vaniljsås"
    assert by_key[("monday", "dinner_main")]["composition_name"] == "Tomatsoppa med ostsmörgås"
    assert by_key[("tuesday", "lunch_alt1")]["unresolved_text"] == "Tisdag okänd rätt alt1"

    second_upload = client_admin.post(
        "/ui/admin/menu-import/upload",
        data={"menu_file": (io.BytesIO(_kommun_w35_csv_bytes()), "kommun_w35.csv")},
        content_type="multipart/form-data",
        headers=ADMIN_HEADERS,
        follow_redirects=True,
    )
    assert second_upload.status_code == 200
    rows_after_reimport = app_session.extensions["builder_menu_context_flow"].list_menu_rows(builder_menu_id)
    assert len(rows_after_reimport) == 28

    db = get_session()
    try:
        link_after_reimport = db.execute(
            text("SELECT builder_menu_version FROM commun_builder_menu_links WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": TENANT_ID, "sid": SITE_ID, "year": YEAR, "week": WEEK},
        ).fetchone()
        assert link_after_reimport is not None
        assert int(link_after_reimport[0]) == 2
    finally:
        db.close()

    week_view = client_admin.get(f"/ui/admin/menu-import/week/{YEAR}/{WEEK}", headers=ADMIN_HEADERS)
    etag = week_view.headers.get("ETag")
    assert etag

    publish_response = client_admin.post(
        f"/ui/admin/menu-import/week/{YEAR}/{WEEK}/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag},
        follow_redirects=True,
    )
    assert publish_response.status_code == 200
    assert "publicerad" in publish_response.data.decode("utf-8").lower()

    db = get_session()
    try:
        publication = db.execute(
            text("SELECT builder_menu_id, builder_menu_version, projection_snapshot_json FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": TENANT_ID, "sid": SITE_ID, "year": YEAR, "week": WEEK},
        ).fetchone()
        assert publication is not None
        assert str(publication[0]) == builder_menu_id
        assert int(publication[1]) == 2
        snapshot = json.loads(str(publication[2]))
        assert len(snapshot["rows"]) == 28
        assert snapshot["rows"][0]["text"] == "Köttbullar med gräddsås och potatis"
    finally:
        db.close()

    scope = DepartmentPortalScope(
        user_id=1,
        role="unit_portal",
        tenant_id=TENANT_ID,
        department_id=DEPARTMENT_ID,
        site_id=SITE_ID,
    )
    payload = build_department_week_payload(scope, YEAR, WEEK)
    assert payload["days"][0]["menu"]["lunch_alt1"] == "Köttbullar med gräddsås och potatis"
    assert payload["days"][0]["menu"]["lunch_alt2"] == "Ugnsbakad lax med dillsås och potatis"
    assert payload["days"][0]["menu"]["dessert"] == "Äppelpaj med vaniljsås"
    assert payload["days"][0]["menu"]["dinner"] == "Tomatsoppa med ostsmörgås"

    from core.weekview_vm import build_weekview_vm

    weekview_vm = build_weekview_vm(site_id=SITE_ID, year=YEAR, week=WEEK, tenant_id=TENANT_ID)
    dep_vm = next(d for d in weekview_vm["departments"] if d["id"] == DEPARTMENT_ID)
    assert dep_vm["days"][0]["menu_texts"]["dinner"]["main"] == "Tomatsoppa med ostsmörgås"
    assert dep_vm["has_dinner"] is True

    report = client_admin.get(f"/ui/reports/weekview?site_id={SITE_ID}&year={YEAR}&week={WEEK}", headers=ADMIN_HEADERS)
    assert report.status_code == 200
    report_html = report.data.decode("utf-8")
    assert "Kvällsmat" in report_html
    assert "Middag" not in report_html

    weekview_ui = client_admin.get(f"/ui/weekview?site_id={SITE_ID}&department_id={DEPARTMENT_ID}&year={YEAR}&week={WEEK}", headers=ADMIN_HEADERS)
    assert weekview_ui.status_code == 200
    weekview_html = weekview_ui.data.decode("utf-8")
    assert "Tomatsoppa med ostsmörgås" in weekview_html
    assert "Kvällsmat" in weekview_html
    assert "Middag" not in weekview_html

    overview = client_admin.get(f"/ui/weekview_overview?site_id={SITE_ID}&year={YEAR}&week={WEEK}", headers=ADMIN_HEADERS)
    assert overview.status_code == 200
    overview_html = overview.data.decode("utf-8")
    assert "Tomatsoppa med ostsmörgås" in overview_html
    assert "Kvällsmat" in overview_html
    assert "Middag" not in overview_html


def test_admin_menu_publish_without_builder_link_fails_closed(app_session):
    site_id = "kommuntesta-no-link"
    year = YEAR
    week = 36

    db = get_session()
    try:
        db.execute(text("DELETE FROM menus WHERE site_id=:sid AND year=:year AND week=:week"), {"sid": site_id, "year": year, "week": week})
        db.execute(text("DELETE FROM commun_builder_menu_links WHERE site_id=:sid AND year=:year AND week=:week"), {"sid": site_id, "year": year, "week": week})
        db.execute(text("DELETE FROM commun_builder_publication_pins WHERE site_id=:sid AND year=:year AND week=:week"), {"sid": site_id, "year": year, "week": week})
        db.execute(text("INSERT OR REPLACE INTO tenants (id, name, active) VALUES (:id, :name, 1)"), {"id": TENANT_ID, "name": "Primary"})
        db.execute(text("INSERT OR REPLACE INTO sites (id, name, tenant_id, version) VALUES (:id, :name, :tid, 0)"), {"id": site_id, "name": "KommunTestA No Link", "tid": TENANT_ID})
        db.execute(
            text("INSERT INTO menus (id, tenant_id, site_id, week, year, status) VALUES (:id, :tid, :sid, :week, :year, :status)"),
            {"id": 999, "tid": TENANT_ID, "sid": site_id, "week": week, "year": year, "status": "draft"},
        )
        db.commit()
    finally:
        db.close()

    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = site_id

    week_view = client.get(f"/ui/admin/menu-import/week/{year}/{week}", headers=ADMIN_HEADERS)
    assert week_view.status_code == 200
    etag = week_view.headers.get("ETag")
    assert etag

    response = client.post(
        f"/ui/admin/menu-import/week/{year}/{week}/publish",
        headers=ADMIN_HEADERS,
        data={"_etag": etag},
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "canonical_publication_missing" in html

    db = get_session()
    try:
        menu_status = db.execute(
            text("SELECT status FROM menus WHERE id=:id"),
            {"id": 999},
        ).fetchone()
        pin = db.execute(
            text("SELECT 1 FROM commun_builder_publication_pins WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"),
            {"tid": TENANT_ID, "sid": site_id, "year": year, "week": week},
        ).fetchone()
        assert menu_status is not None and menu_status[0] == "draft"
        assert pin is None
    finally:
        db.close()