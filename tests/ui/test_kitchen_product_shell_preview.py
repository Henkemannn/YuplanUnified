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
    assert "app-shell--kitchen-product" not in html


def test_kitchen_planering_product2_renders_shell_preview_only(client_admin):
    site_id = _seed_site(client_admin.application)

    rv = client_admin.get(
        f"/ui/kitchen/planering?ui=product2&site_id={site_id}",
        headers=_headers(),
    )
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "app-shell--kitchen-product" in html
    assert "Product shell preview" in html
    assert 'class="app-shell__brand-copy"' in html
    assert "<strong>Yuplan</strong>" in html
    assert "· Planera" in html
    assert "LOCAL" not in html
    assert "planera-day-product2" not in html
    assert "Välj dag och måltid" not in html


def test_product2_css_does_not_style_shell_selectors():
    css = Path("static/css/planera_day_product2.css").read_text(encoding="utf-8")
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