import json
import re
from datetime import date as _date, timedelta
from html import unescape
from pathlib import Path

import pytest
from flask import current_app
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
from core.admin_repo import SitesRepo
from core.commun_builder_linkage import CommunBuilderMenuLinkService
from core.db import create_all, get_session
from core.menu import InMemoryCompositionAliasRepository, MenuService
from core.menu_service import MenuServiceDB
from core.ui_blueprint import _apply_builder_reader_weekview_overview, _build_product2_page1_menu_vm
from sqlalchemy import text


class _FixedToday(_date):
    @classmethod
    def today(cls):
        return cls(2026, 9, 21)


def _headers(role: str = "admin", tenant_id: str | None = "1") -> dict[str, str]:
    headers = {"X-User-Role": role}
    if tenant_id is not None:
        headers["X-Tenant-Id"] = tenant_id
    return headers


def _seed_site(app, *, site_name: str = "Preview Site", tenant_id: int = 1) -> str:
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(
                text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(:id, :name, 1)"),
                {"id": tenant_id, "name": f"Tenant {tenant_id}"},
            )
            db.commit()
        finally:
            db.close()
        site, _ = SitesRepo().create_site(name=site_name, tenant_id=tenant_id)
    return site["id"]


def _build_builder_menu_context_flow() -> tuple[BuilderMenuContextFlow, CompositionService]:
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
    return menu_context_flow, CompositionService(repository=composition_repository)


def _seed_product2_publication(
    app,
    *,
    site_id: str,
    year: int,
    week: int,
    builder_menu_id: str,
    builder_menu_version: int = 1,
    lunch_rows: list[dict[str, object]] | None = None,
) -> None:
    rows = lunch_rows or [
        {
            "day": "monday",
            "meal_slot": "lunch_alt1",
            "composition_id": "comp-product2-mon",
            "composition_name": "Måndagssoppa",
            "sort_order": 5,
        },
        {
            "day": "tuesday",
            "meal_slot": "lunch_alt1",
            "composition_id": "comp-product2-tue-a",
            "composition_name": "Publicerad rätt A",
            "sort_order": 10,
        },
        {
            "day": "tuesday",
            "meal_slot": "lunch_alt2",
            "composition_id": "comp-product2-tue-b",
            "composition_name": "Publicerad rätt B",
            "sort_order": 20,
        },
    ]
    with app.app_context():
        builder_flow, composition_service = _build_builder_menu_context_flow()
        current_app.extensions["builder_menu_context_flow"] = builder_flow
        current_app.extensions["builder_flow"] = builder_flow
        builder_flow.create_menu(
            menu_id=builder_menu_id,
            site_id=site_id,
            week_key=f"{year}-W{week:02d}",
            version=builder_menu_version,
            status="published",
        )
        for index, row in enumerate(rows, start=1):
            composition_id = str(row["composition_id"])
            composition_service.create_composition(
                composition_id=composition_id,
                composition_name=str(row["composition_name"]),
            )
            builder_flow.add_composition_menu_row(
                menu_id=builder_menu_id,
                menu_detail_id=f"detail-{index}",
                day=str(row["day"]),
                meal_slot=str(row["meal_slot"]),
                composition_id=composition_id,
                sort_order=int(row["sort_order"]),
            )
        legacy_menu = MenuServiceDB().create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year)
        CommunBuilderMenuLinkService(builder_menu_context_flow=builder_flow).create_or_replace_link(
            tenant_id=1,
            site_id=site_id,
            year=year,
            week=week,
            builder_menu_id=builder_menu_id,
            legacy_menu_id=legacy_menu.id,
            source="manual",
        )
        MenuServiceDB().publish_menu(tenant_id=1, menu_id=legacy_menu.id)


def _seed_product2_legacy_only_menu(
    app,
    *,
    site_id: str,
    year: int,
    week: int,
) -> int:
    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text("INSERT OR IGNORE INTO dishes(id, tenant_id, name, category) VALUES(:id, :tid, :name, :category)"),
                {"id": 99001, "tid": 1, "name": "Legacy alt1", "category": "test"},
            )
            db.execute(
                text("INSERT OR IGNORE INTO dishes(id, tenant_id, name, category) VALUES(:id, :tid, :name, :category)"),
                {"id": 99002, "tid": 1, "name": "Legacy alt2", "category": "test"},
            )
            db.commit()
        finally:
            db.close()
        menu = MenuServiceDB().create_or_get_menu(tenant_id=1, site_id=site_id, week=week, year=year)
        legacy_menu_service = MenuServiceDB()
        legacy_menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="tuesday", meal="lunch", variant_type="alt1", dish_id=99001)
        legacy_menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="tuesday", meal="lunch", variant_type="alt2", dish_id=99002)
        return menu.id


def _product2_html(client_admin, site_id: str, *, headers: dict[str, str] | None = None, query: str = "") -> str:
    rv = client_admin.get(
        f"/ui/kitchen/planering?ui=product2&site_id={site_id}{query}",
        headers=headers or _headers(),
    )
    assert rv.status_code == 200
    return unescape(rv.get_data(as_text=True))


def _product2_url(site_id: str, *, year: int, week: int, day: int) -> str:
    return f"/ui/kitchen/planering?ui=product2&site_id={site_id}&year={year}&week={week}&day={day}"


def _weekbar_href(html: str, label: str) -> str:
    match = re.search(rf'<a class="yp-planera-page1-weekbar__arrow" href="([^"]+)" aria-label="{re.escape(label)}">', html)
    assert match, f"missing {label} link"
    return match.group(1)


def test_kitchen_planering_v1_remains_default(client_admin):
    rv = client_admin.get("/ui/kitchen/planering", headers=_headers())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Välj dag och måltid" in html
    assert "yp-product-shell" not in html
    assert "css/app_shell.css" in html
    assert "css/kitchen_product_shell.css" not in html


def test_kitchen_planering_product2_renders_shell_preview_only(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Skärgårdsköket")
    html = _product2_html(client_admin, site_id)
    assert "yp-product-shell" in html
    assert "yp-product-app" in html
    assert "yp-product-topbar" in html
    assert "yp-product-panel-inner" in html
    assert "yp-planera-page1" in html
    assert "yp-planera-page1-layout" in html
    assert "yp-planera-page1-sidebar" in html
    assert "yp-planera-page1-main" in html
    assert "yp-planera-page1-weekbar" in html
    assert "yp-planera-page1-lunch" in html
    assert "yp-planera-page1-secondary" in html
    assert "id=\"yp-product-app\"" in html
    assert "css/kitchen_product_shell.css" in html
    assert "css/planera_product2_page1.css" in html
    assert "css/app_shell.css" not in html
    assert "css/planera_day_product2.css" not in html
    assert "/static/js/kitchen_product_shell.js" in html or "js/kitchen_product_shell.js" in html
    assert "app_shell.js" not in html
    assert "YUPLAN APP SHELL — LOCKED" in html
    assert "Skärgårdsköket" in html
    assert "Kommun" in html
    assert "HJ" in html
    assert "18 mottagande enheter · 273 portioner" in html
    assert "Ingen publicerad lunchmeny" in html
    assert "Fläskkarré" not in html
    assert "Kokt torsk" not in html
    assert "KVÄLL" in html
    assert "Köttfärssoppa" in html
    assert "DESSERT" in html
    assert "Äppelpaj" in html
    assert "TILLÄGG" in html
    assert "Sallad · Mos · Övriga tillval" in html
    assert "Planera lunch →" in html
    assert html.index('id="yp-product-app"') < html.index('class="yp-product-topbar"')
    assert html.index('class="yp-product-topbar"') < html.index('class="yp-product-panel"')
    assert html.index('class="yp-product-panel"') < html.index('class="yp-product-panel-inner"')
    assert html.index('class="yp-product-panel-inner"') < html.index('class="yp-planera-page1"')
    assert html.index('class="yp-planera-page1"') < html.index('class="yp-planera-page1-layout"')
    assert html.index('class="yp-planera-page1-layout"') < html.index('class="yp-planera-page1-sidebar"')
    assert html.index('class="yp-planera-page1-sidebar"') < html.index('class="yp-planera-page1-main"')
    assert html.index('class="yp-planera-page1-main"') < html.index('class="yp-planera-page1-weekbar"')
    assert "product-shell-preview-marker" not in html
    assert "yp-product-planera-start" not in html
    assert "yp-product-planera-start__weekbar" not in html
    assert "yp-product-planera-start__lunch" not in html
    assert "yp-product-planera-start__secondary" not in html
    assert "yp-product-planera-start__date" not in html
    assert "yp-product-cta" not in html
    assert 'class="yp-product-topbar-brand__copy"' in html
    assert "<strong>Yuplan</strong>" in html
    assert "· Planera" in html
    assert "LOCAL" not in html
    assert "app-shell" not in html
    assert "planera-day-product2" not in html
    assert "Välj dag och måltid" not in html
    assert "Probe site" not in html


def test_kitchen_planering_product2_published_lunch_renders_publication_titles(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Published Lunch Site")
    _seed_product2_publication(
        client_admin.application,
        site_id=site_id,
        year=2026,
        week=40,
        builder_menu_id="builder-menu-product2",
        builder_menu_version=1,
    )

    html = _product2_html(client_admin, site_id, query="&year=2026&week=40&day=1")

    assert "Publicerad rätt A" in html
    assert "Publicerad rätt B" in html
    assert "Fläskkarré" not in html
    assert "Kokt torsk" not in html
    assert html.index("Publicerad rätt A") < html.index("Publicerad rätt B")


def test_kitchen_planering_product2_three_option_lunch_renders_collection(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Three Option Site")
    _seed_product2_publication(
        client_admin.application,
        site_id=site_id,
        year=2026,
        week=40,
        builder_menu_id="builder-menu-product2-three",
        builder_menu_version=1,
        lunch_rows=[
            {
                "day": "monday",
                "meal_slot": "lunch_alt1",
                "composition_id": "comp-product2-mon",
                "composition_name": "Måndagssoppa",
                "sort_order": 5,
            },
            {
                "day": "tuesday",
                "meal_slot": "lunch_alt1",
                "composition_id": "comp-product2-three-a",
                "composition_name": "Publicerad rätt A",
                "sort_order": 10,
            },
            {
                "day": "tuesday",
                "meal_slot": "lunch_alt2",
                "composition_id": "comp-product2-three-b",
                "composition_name": "Publicerad rätt B",
                "sort_order": 20,
            },
            {
                "day": "tuesday",
                "meal_slot": "lunch_alt3",
                "composition_id": "comp-product2-three-c",
                "composition_name": "Publicerad rätt C",
                "sort_order": 30,
            },
        ],
    )

    html = _product2_html(client_admin, site_id, query="&year=2026&week=40&day=1")

    assert "Publicerad rätt A" in html
    assert "Publicerad rätt B" in html
    assert "Publicerad rätt C" in html
    assert html.index("Publicerad rätt A") < html.index("Publicerad rätt B") < html.index("Publicerad rätt C")
    assert html.count("yp-planera-page1-option") >= 3


def test_kitchen_planering_product2_unresolved_free_text_renders_exactly(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Free Text Site")
    _seed_product2_publication(
        client_admin.application,
        site_id=site_id,
        year=2026,
        week=40,
        builder_menu_id="builder-menu-product2-free-text",
        builder_menu_version=1,
    )

    db = get_session()
    try:
        row = db.execute(
            text(
                "SELECT projection_snapshot_json FROM commun_builder_publication_pins "
                "WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"
            ),
            {"tid": 1, "sid": site_id, "year": 2026, "week": 40},
        ).fetchone()
        assert row is not None
        snapshot = json.loads(str(row[0]))
        for item in snapshot["rows"]:
            if str(item.get("day")) == "tuesday" and str(item.get("variant_type")) == "alt2":
                item["resolved"] = False
                item["text"] = "Vegetarisk lasagne"
                item["unresolved_text"] = "Vegetarisk lasagne"
                break
        db.execute(
            text(
                "UPDATE commun_builder_publication_pins SET projection_snapshot_json=:snapshot "
                "WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"
            ),
            {"snapshot": json.dumps(snapshot, ensure_ascii=False), "tid": 1, "sid": site_id, "year": 2026, "week": 40},
        )
        db.commit()
    finally:
        db.close()

    html = _product2_html(client_admin, site_id, query="&year=2026&week=40&day=1")

    assert "Vegetarisk lasagne" in html
    assert "Kokt torsk" not in html


def test_kitchen_planering_product2_dynamic_frame_uses_selected_date_and_weekdays(client_admin, monkeypatch):
    monkeypatch.setattr("core.ui_blueprint._date", _FixedToday)
    site_id = _seed_site(client_admin.application, site_name="Frame Site")
    html = _product2_html(client_admin, site_id, query="&year=2026&week=39&day=1")

    assert "Frame Site" in html
    assert "Tisdag 22 september" in html
    assert "Vecka 39" in html
    assert "class=\"yp-planera-page1-weekday is-current\"" in html
    assert "aria-current=\"date\"" in html

    weekday_entries = re.findall(
        r'<button class="([^"]*yp-planera-page1-weekday[^"]*)" type="button"(?: aria-current="date")?>\s*<span>([^<]+)</span><strong>(\d+)</strong>\s*</button>',
        html,
        flags=re.S,
    )
    assert weekday_entries == [
        ("yp-planera-page1-weekday is-today", "Mån", "21"),
        ("yp-planera-page1-weekday is-current", "Tis", "22"),
        ("yp-planera-page1-weekday", "Ons", "23"),
        ("yp-planera-page1-weekday", "Tor", "24"),
        ("yp-planera-page1-weekday", "Fre", "25"),
        ("yp-planera-page1-weekday", "Lör", "26"),
        ("yp-planera-page1-weekday", "Sön", "27"),
    ]


def test_kitchen_planering_product2_today_state_is_marked(client_admin, monkeypatch):
    monkeypatch.setattr("core.ui_blueprint._date", _FixedToday)
    site_id = _seed_site(client_admin.application, site_name="Today Site")
    html = _product2_html(client_admin, site_id, query="&year=2026&week=39")

    assert "Måndag 21 september" in html
    assert "class=\"yp-planera-page1-weekday is-current is-today\"" in html
    assert "aria-current=\"date\"" in html


def test_kitchen_planering_product2_rollover_navigation_targets_preserve_selected_day(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Rollover Site")
    year = 2026
    week = 1
    day = 3
    html = _product2_html(client_admin, site_id, query=f"&year={year}&week={week}&day={day}")

    monday = _date.fromisocalendar(year, week, 1)
    prev_iso = (monday - timedelta(days=7)).isocalendar()
    next_iso = (monday + timedelta(days=7)).isocalendar()
    prev_href = _weekbar_href(html, "Föregående vecka")
    next_href = _weekbar_href(html, "Nästa vecka")

    assert prev_href == _product2_url(site_id, year=prev_iso[0], week=prev_iso[1], day=day)
    assert next_href == _product2_url(site_id, year=next_iso[0], week=next_iso[1], day=day)
    assert "onclick=\"location.href" not in html
    assert 'javascript:' not in html


def test_kitchen_planering_product2_weekbar_hrefs_preserve_product2_context(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Href Site")
    html = _product2_html(client_admin, site_id, query="&year=2026&week=39&day=1")

    prev_href = _weekbar_href(html, "Föregående vecka")
    next_href = _weekbar_href(html, "Nästa vecka")

    assert "ui=product2" in prev_href
    assert f"site_id={site_id}" in prev_href
    assert "day=1" in prev_href
    assert "ui=product2" in next_href
    assert f"site_id={site_id}" in next_href
    assert "day=1" in next_href
    assert "onclick=\"location.href" not in html


def test_kitchen_planering_product2_missing_tenant_fails_closed(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Tenant Guard Site")
    fresh_client = client_admin.application.test_client()
    rv = fresh_client.get(
        f"/ui/kitchen/planering?ui=product2&site_id={site_id}",
        headers=_headers(tenant_id=None),
    )
    assert rv.status_code == 404


def test_kitchen_planering_product2_published_menu_seam_uses_projection(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Published Menu Site")
    _seed_product2_publication(
        client_admin.application,
        site_id=site_id,
        year=2026,
        week=40,
        builder_menu_id="builder-menu-product2",
        builder_menu_version=1,
    )

    vm = _build_product2_page1_menu_vm(
        tenant_id=1,
        site_id=site_id,
        year=2026,
        week=40,
        selected_day=1,
    )

    assert vm["status"] == "ok"
    lunch = vm["lunch"]
    assert lunch is not None
    assert lunch.meal == "lunch"
    assert [option.option_id for option in lunch.options] == ["detail-2", "detail-3"]
    assert [option.display_title for option in lunch.options] == ["Publicerad rätt A", "Publicerad rätt B"]
    assert [option.sort_order for option in lunch.options] == [10, 20]
    assert [option.variant_type for option in lunch.options] == ["alt1", "alt2"]


def test_kitchen_planering_product2_no_publication_does_not_fall_back_to_legacy(client_admin):
    site_id = _seed_site(client_admin.application, site_name="No Publication Site")
    _seed_product2_legacy_only_menu(
        client_admin.application,
        site_id=site_id,
        year=2026,
        week=41,
    )

    vm = _build_product2_page1_menu_vm(
        tenant_id=1,
        site_id=site_id,
        year=2026,
        week=41,
        selected_day=1,
    )

    assert vm["status"] == "no_publication"
    assert vm["lunch"] is None


def test_kitchen_planering_product2_bad_publication_fails_closed(client_admin):
    site_id = _seed_site(client_admin.application, site_name="Bad Publication Site")
    _seed_product2_publication(
        client_admin.application,
        site_id=site_id,
        year=2026,
        week=42,
        builder_menu_id="builder-menu-product2-bad",
        builder_menu_version=1,
    )

    db = get_session()
    try:
        row = db.execute(
            text(
                "SELECT projection_snapshot_json FROM commun_builder_publication_pins "
                "WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"
            ),
            {"tid": 1, "sid": site_id, "year": 2026, "week": 42},
        ).fetchone()
        assert row is not None
        snapshot = json.loads(str(row[0]))
        snapshot["rows"][1]["variant_type"] = "unresolved_variant"
        db.execute(
            text(
                "UPDATE commun_builder_publication_pins SET projection_snapshot_json=:snapshot "
                "WHERE tenant_id=:tid AND site_id=:sid AND year=:year AND week=:week"
            ),
            {"snapshot": json.dumps(snapshot, ensure_ascii=False), "tid": 1, "sid": site_id, "year": 2026, "week": 42},
        )
        db.commit()
    finally:
        db.close()

    with pytest.raises(RuntimeError, match="product2_menu_contract_error"):
        _build_product2_page1_menu_vm(
            tenant_id=1,
            site_id=site_id,
            year=2026,
            week=42,
            selected_day=1,
        )


def test_kitchen_planering_product2_cross_tenant_site_fails_closed(client_admin):
    app = client_admin.application
    site_id = None
    tenant2_created = False
    with app.app_context():
        db = get_session()
        try:
            tenant2 = db.execute(text("SELECT id FROM tenants WHERE id=:id"), {"id": 2}).fetchone()
            if tenant2 is None:
                db.execute(text("INSERT INTO tenants(id, name, active) VALUES(2, 'Tenant 2', 1)"))
                tenant2_created = True
                db.commit()
            site, _ = SitesRepo().create_site(name="Other Tenant Site", tenant_id=2)
            site_id = site["id"]
            db.commit()
        finally:
            db.close()

    try:
        fresh_client = app.test_client()
        rv = fresh_client.get(
            f"/ui/kitchen/planering?ui=product2&site_id={site_id}",
            headers=_headers(tenant_id="1"),
        )
        assert rv.status_code == 404
    finally:
        with app.app_context():
            db = get_session()
            try:
                if site_id is not None:
                    db.execute(text("DELETE FROM sites WHERE id=:id"), {"id": site_id})
                if tenant2_created:
                    db.execute(text("DELETE FROM tenants WHERE id=2"))
                db.commit()
            finally:
                db.close()


def test_product2_css_does_not_style_shell_selectors():
    css = Path("static/css/kitchen_product_shell.css").read_text(encoding="utf-8")
    forbidden_selectors = [
        ".app-shell",
        ".app-shell__topbar",
        ".app-shell__brand",
        ".app-shell__body",
        ".app-shell__sidebar",
        ".app-shell__sidebar-panel",
        ".app-shell__nav",
        ".app-shell__nav-item",
        ".app-shell__main",
    ]
    for selector in forbidden_selectors:
        assert selector not in css


def test_product2_shell_styles_are_isolated_from_shared_shell_css():
    shared_css = Path("static/css/app_shell.css").read_text(encoding="utf-8")
    product_css = Path("static/css/kitchen_product_shell.css").read_text(encoding="utf-8")

    assert ".yp-product-shell" not in shared_css
    assert ".yp-product-shell" in product_css
    assert ".app-shell--kitchen-product" not in product_css


def test_product2_page_css_is_page_only():
    css = Path("static/css/planera_product2_page1.css").read_text(encoding="utf-8")

    forbidden_selectors = [
        ".yp-product-shell",
        ".yp-product-app",
        ".yp-product-topbar",
        ".yp-product-panel",
        ".yp-product-panel-inner",
        ".yp-product-sidebar",
        ".yp-product-main-content",
    ]
    for selector in forbidden_selectors:
        assert selector not in css
    for selector in [
        ".yp-planera-page1",
        ".yp-planera-page1-layout",
        ".yp-planera-page1-sidebar",
        ".yp-planera-page1-main",
        ".yp-planera-page1-weekbar",
        ".yp-planera-page1-lunch",
        ".yp-planera-page1-secondary",
    ]:
        assert selector in css