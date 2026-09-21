import re
from datetime import date as _date, timedelta
from html import unescape
from pathlib import Path

from core.admin_repo import SitesRepo
from core.db import create_all, get_session
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
    assert "Fläskkarré" in html
    assert "Potatismos · Gräddsås" in html
    assert "Kokt torsk" in html
    assert "Äggsås · Kokt potatis" in html
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