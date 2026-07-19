from __future__ import annotations

import uuid

from sqlalchemy import text

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Site, Tenant, TenantFeatureFlag


def _headers(role: str, tenant_id: int = 1):
    return {"X-User-Role": role, "X-Tenant-Id": str(tenant_id), "X-User-Id": "42"}


def _mk_app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with app.app_context():
        create_all()
        db = get_session()
        try:
            if not db.query(Tenant).filter_by(id=1).first():
                db.add(Tenant(id=1, name="Tenant One"))
            if not db.query(Tenant).filter_by(id=2).first():
                db.add(Tenant(id=2, name="Tenant Two"))
            db.commit()
        finally:
            db.close()
    app.feature_registry.set("offshore.v2.enabled", True)
    return app


def _seed_site(app, *, tenant_id: int, name: str) -> str:
    site_id = str(uuid.uuid4())
    with app.app_context():
        db = get_session()
        try:
            db.add(Site(id=site_id, name=name, tenant_id=tenant_id))
            db.commit()
        finally:
            db.close()
    return site_id


def _login(client, *, tenant_id: int, site_id: str, role: str):
    with client.session_transaction() as sess:
        sess["tenant_id"] = tenant_id
        sess["site_id"] = site_id
        sess["user_id"] = 42
        sess["role"] = role
        sess["full_name"] = "Henrik"


def test_settings_page_renders_real_forms():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")

    response = client.get("/offshore/settings", headers=_headers("admin"))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "name=\"timezone\"" in html
    assert "Arbetspositioner" in html or "Work positions" in html
    assert "Menycykel" in html
    assert "create_work_position" not in html


def test_installation_settings_create_update_and_dashboard_state():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")

    response = client.post(
        "/offshore/settings/installation",
        data={
            "timezone": "Europe/Oslo",
            "default_locale": "no",
            "default_theme": "dark",
            "default_portions": "120",
            "is_active": "1",
        },
        headers=_headers("admin"),
    )
    assert response.status_code == 302

    with app.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT timezone, default_locale, default_theme, default_portions, is_active FROM offshore_installation_settings WHERE tenant_id=1 AND site_id=:sid"), {"sid": site_id}).fetchone()
            assert row == ("Europe/Oslo", "no", "dark", 120, 1)
        finally:
            db.close()

    dashboard = client.get("/offshore", headers=_headers("admin"))
    assert dashboard.status_code == 200
    html = dashboard.get_data(as_text=True)
    assert "Installation konfigurerad" in html or "Installation configured" in html
    assert "0 aktiva arbetspositioner" in html or "0 active work positions" in html


def test_installation_validation_rejects_invalid_values():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")

    for payload in [
        {"timezone": "Not/AZone", "default_locale": "sv", "default_theme": "system", "default_portions": "1"},
        {"timezone": "Europe/Oslo", "default_locale": "xx", "default_theme": "system", "default_portions": "1"},
        {"timezone": "Europe/Oslo", "default_locale": "sv", "default_theme": "purple", "default_portions": "1"},
        {"timezone": "Europe/Oslo", "default_locale": "sv", "default_theme": "system", "default_portions": "0"},
    ]:
        response = client.post("/offshore/settings/installation", data=payload, headers=_headers("admin"))
        assert response.status_code == 302
        assert response.headers.get("Location", "").endswith("/offshore/settings")


def test_work_positions_create_toggle_and_move():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")

    client.post(
        "/offshore/settings/work-positions",
        data={"name": "Kokk 1", "position_type": "cook", "code": "kokk-1"},
        headers=_headers("admin"),
    )
    client.post(
        "/offshore/settings/work-positions",
        data={"name": "Kokk 2", "position_type": "cook", "code": "kokk-2"},
        headers=_headers("admin"),
    )
    client.post(
        "/offshore/settings/work-positions/2/move-up",
        headers=_headers("admin"),
    )
    client.post(
        "/offshore/settings/work-positions/1/toggle",
        headers=_headers("admin"),
    )
    client.post(
        "/offshore/settings/work-positions/2/update",
        data={"name": "Kokk 2 Updated", "position_type": "cook", "description": "Updated"},
        headers=_headers("admin"),
    )

    duplicate = client.post(
        "/offshore/settings/work-positions",
        data={"name": "Kokk 1 again", "position_type": "cook", "code": "kokk-1"},
        headers=_headers("admin"),
    )
    assert duplicate.status_code == 302

    with app.app_context():
        db = get_session()
        try:
            rows = db.execute(text("SELECT name, code, sort_order, is_active FROM offshore_work_positions WHERE tenant_id=1 AND site_id=:sid ORDER BY sort_order, id"), {"sid": site_id}).fetchall()
            assert [row[0] for row in rows] == ["Kokk 2 Updated", "Kokk 1"]
            assert [row[2] for row in rows] == [1, 2]
            assert rows[0][1] == "kokk-2"
            assert rows[1][3] == 0
        finally:
            db.close()


def test_work_position_duplicate_code_rejected_and_cross_site_404():
    app = _mk_app()
    site_a = _seed_site(app, tenant_id=1, name="Rig A")
    site_b = _seed_site(app, tenant_id=1, name="Rig B")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_a, role="admin")

    client.post("/offshore/settings/work-positions", data={"name": "Lead", "position_type": "lead", "code": "lead-1"}, headers=_headers("admin"))
    duplicate = client.post("/offshore/settings/work-positions", data={"name": "Lead 2", "position_type": "lead", "code": "lead-1"}, headers=_headers("admin"))
    assert duplicate.status_code == 302

    with app.app_context():
        db = get_session()
        try:
            count = db.execute(text("SELECT COUNT(*) FROM offshore_work_positions WHERE tenant_id=1 AND site_id=:sid"), {"sid": site_a}).scalar_one()
            assert count == 1
        finally:
            db.close()

    other_site_client = app.test_client()
    _login(other_site_client, tenant_id=1, site_id=site_b, role="admin")
    missing = other_site_client.post("/offshore/settings/work-positions/1/update", data={"name": "X", "position_type": "lead"}, headers=_headers("admin"))
    assert missing.status_code == 404


def test_work_position_code_stays_stable_after_display_name_change():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")

    client.post("/offshore/settings/work-positions", data={"name": "Dagkock A", "position_type": "cook", "code": "dagkock-a"}, headers=_headers("admin"))
    client.post("/offshore/settings/work-positions/1/update", data={"name": "Dagkock A2", "position_type": "cook"}, headers=_headers("admin"))

    with app.app_context():
        db = get_session()
        try:
            row = db.execute(text("SELECT code, name FROM offshore_work_positions WHERE tenant_id=1 AND site_id=:sid AND id=1"), {"sid": site_id}).fetchone()
            assert row == ("dagkock-a", "Dagkock A2")
        finally:
            db.close()


def test_menu_cycle_create_resize_and_slot_labels():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="admin")

    client.post(
        "/offshore/settings/menu-cycle",
        data={"name": "Ordinarie menycykel", "cycle_length": "4", "is_active": "1"},
        headers=_headers("admin"),
    )
    client.post(
        "/offshore/settings/menu-cycle/1/slots/1/update",
        data={"label": "Meny A", "description": "Første"},
        headers=_headers("admin"),
    )
    client.post(
        "/offshore/settings/menu-cycle/1/update",
        data={"name": "Ordinarie menycykel", "cycle_length": "6"},
        headers=_headers("admin"),
    )
    client.post(
        "/offshore/settings/menu-cycle",
        data={"name": "Sekundär", "cycle_length": "2", "is_active": "1"},
        headers=_headers("admin"),
    )
    other_site_client = app.test_client()
    other_site_id = _seed_site(app, tenant_id=1, name="Rig C")
    _login(other_site_client, tenant_id=1, site_id=other_site_id, role="admin")
    other_site_client.post(
        "/offshore/settings/menu-cycle",
        data={"name": "Other cycle", "cycle_length": "3", "is_active": "1"},
        headers=_headers("admin"),
    )

    with app.app_context():
        db = get_session()
        try:
            cycle_rows = db.execute(text("SELECT id, name, cycle_length, is_active FROM offshore_menu_cycles WHERE tenant_id=1 AND site_id=:sid ORDER BY id"), {"sid": site_id}).fetchall()
            assert len(cycle_rows) == 2
            assert cycle_rows[-1][3] == 1
            assert cycle_rows[0][3] == 0
            slot_rows = db.execute(text("SELECT cycle_index, label FROM offshore_menu_cycle_slots WHERE tenant_id=1 AND site_id=:sid AND menu_cycle_id=:cycle_id ORDER BY cycle_index"), {"sid": site_id, "cycle_id": cycle_rows[0][0]}).fetchall()
            assert len(slot_rows) == 6
            assert slot_rows[0][1] == "Meny A"
            assert [row[0] for row in slot_rows] == [1, 2, 3, 4, 5, 6]
            other_rows = db.execute(text("SELECT COUNT(*) FROM offshore_menu_cycles WHERE tenant_id=1 AND site_id=:sid"), {"sid": other_site_id}).fetchone()
            assert other_rows[0] == 1
        finally:
            db.close()


def test_menu_cycle_validation_and_403_forbidden_post():
    app = _mk_app()
    site_id = _seed_site(app, tenant_id=1, name="Rig A")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_id, role="viewer")

    forbidden = client.post(
        "/offshore/settings/menu-cycle",
        data={"name": "View Only", "cycle_length": "4", "is_active": "1"},
        headers=_headers("viewer"),
    )
    assert forbidden.status_code == 403

    admin_client = app.test_client()
    _login(admin_client, tenant_id=1, site_id=site_id, role="admin")
    bad = admin_client.post(
        "/offshore/settings/menu-cycle",
        data={"name": "Bad", "cycle_length": "0", "is_active": "1"},
        headers=_headers("admin"),
    )
    assert bad.status_code == 302


def test_rbac_and_cross_site_protection():
    app = _mk_app()
    site_a = _seed_site(app, tenant_id=1, name="Rig A")
    site_b = _seed_site(app, tenant_id=1, name="Rig B")
    client = app.test_client()
    _login(client, tenant_id=1, site_id=site_a, role="viewer")

    denied = client.post(
        "/offshore/settings/work-positions",
        data={"name": "Viewer Pos", "position_type": "cook"},
        headers=_headers("viewer"),
    )
    assert denied.status_code == 403

    admin_client = app.test_client()
    _login(admin_client, tenant_id=1, site_id=site_a, role="admin")
    admin_client.post(
        "/offshore/settings/work-positions",
        data={"name": "Site A Pos", "position_type": "cook", "code": "site-a-pos"},
        headers=_headers("admin"),
    )
    other_site_client = app.test_client()
    _login(other_site_client, tenant_id=1, site_id=site_b, role="admin")
    cross_site = other_site_client.post(
        "/offshore/settings/work-positions/1/update",
        data={"name": "Wrong Site", "position_type": "cook"},
        headers=_headers("admin"),
    )
    assert cross_site.status_code == 404
