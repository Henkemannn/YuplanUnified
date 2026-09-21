from pathlib import Path

from core.admin_repo import SitesRepo
from core.db import create_all


def _headers(role: str = "admin", tenant_id: str = "1") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": tenant_id}


def _seed_site(app, *, site_name: str = "Preview Site") -> str:
    with app.app_context():
        create_all()
        site, _ = SitesRepo().create_site(name=site_name, tenant_id=1)
    return site["id"]


def test_kitchen_planering_v1_remains_default(client_admin):
    rv = client_admin.get("/ui/kitchen/planering", headers=_headers())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Välj dag och måltid" in html
    assert "yp-product-shell" not in html
    assert "css/app_shell.css" in html
    assert "css/kitchen_product_shell.css" not in html


def test_kitchen_planering_product2_renders_shell_preview_only(client_admin):
    site_id = _seed_site(client_admin.application)

    rv = client_admin.get(
        f"/ui/kitchen/planering?ui=product2&site_id={site_id}",
        headers=_headers(),
    )
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "yp-product-shell" in html
    assert "yp-product-app" in html
    assert "yp-product-topbar" in html
    assert "yp-product-panel-inner" in html
    assert "yp-product-layout" in html
    assert "yp-product-sidebar" in html
    assert "yp-product-nav" in html
    assert "yp-product-main-content" in html
    assert "id=\"yp-product-app\"" in html
    assert "css/kitchen_product_shell.css" in html
    assert "css/app_shell.css" not in html
    assert "css/planera_day_product2.css" not in html
    assert "/static/js/kitchen_product_shell.js" in html or "js/kitchen_product_shell.js" in html
    assert "app_shell.js" not in html
    assert "YUPLAN APP SHELL — LOCKED" in html
    assert "Product shell preview" in html
    assert "product-shell-preview-marker" in html
    assert html.index('id="yp-product-app"') < html.index('class="yp-product-topbar"')
    assert html.index('class="yp-product-topbar"') < html.index('class="yp-product-panel"')
    assert html.index('class="yp-product-panel"') < html.index('class="yp-product-panel-inner"')
    assert html.index('class="yp-product-panel-inner"') < html.index('class="yp-product-layout"')
    assert html.index('class="yp-product-layout"') < html.index('class="yp-product-sidebar"')
    assert html.index('class="yp-product-sidebar"') < html.index('class="yp-product-main-content"')
    assert "yp-product-planera-start" not in html
    assert "yp-product-planera-start__weekbar" not in html
    assert "yp-product-planera-start__lunch" not in html
    assert "yp-product-planera-start__secondary" not in html
    assert "yp-product-planera-start__date" not in html
    assert "yp-product-cta" not in html
    assert "ALT 1" not in html
    assert "ALT 2" not in html
    assert "Planera lunch" not in html
    assert "Köttfärssoppa" not in html
    assert "Äppelpaj" not in html
    assert 'class="yp-product-topbar-brand__copy"' in html
    assert "<strong>Yuplan</strong>" in html
    assert "· Planera" in html
    assert "LOCAL" not in html
    assert "app-shell" not in html
    assert "planera-day-product2" not in html
    assert "Välj dag och måltid" not in html


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