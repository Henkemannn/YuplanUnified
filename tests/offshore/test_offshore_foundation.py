from __future__ import annotations

import uuid

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Site, Tenant, TenantFeatureFlag
from sqlalchemy import text


def _h(role: str):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _enable(app, name: str, enabled: bool = True):
    reg = app.feature_registry
    if not reg.has(name):
        reg.add(name)
    reg.set(name, enabled)


def _mk_app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with app.app_context():
        create_all()
        db = get_session()
        try:
            if not db.query(Tenant).filter_by(id=1).first():
                db.add(Tenant(id=1, name="Tenant One"))
            db.commit()
        finally:
            db.close()
    return app


def _seed_site(app, *, tenant_id: int = 1, site_name: str = "Rigg X") -> str:
    site_id = str(uuid.uuid4())
    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text("INSERT INTO sites(id, name, tenant_id, version) VALUES(:id,:name,:tenant_id,0)"),
                {"id": site_id, "name": site_name, "tenant_id": tenant_id},
            )
            db.commit()
        finally:
            db.close()
    return site_id


def test_offshore_flag_off_returns_404():
    app = _mk_app()
    _enable(app, "offshore.v2.enabled", False)
    client = app.test_client()
    r = client.get("/offshore", headers=_h("admin"))
    assert r.status_code == 404


def test_legacy_offshore_ping_coexists_with_v2_routes():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": "sqlite:///:memory:",
            "default_enabled_modules": ["municipal", "offshore"],
        }
    )
    with app.app_context():
        create_all()
        db = get_session()
        try:
            if not db.query(Tenant).filter_by(id=1).first():
                db.add(Tenant(id=1, name="Tenant One"))
            db.commit()
        finally:
            db.close()
    _enable(app, "offshore.v2.enabled", True)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = _seed_site(app)
        sess["tenant_id"] = 1
        sess["user_id"] = 99
        sess["role"] = "admin"
    legacy = client.get("/offshore/ping", headers=_h("admin"))
    assert legacy.status_code == 200
    assert legacy.get_json() == {"module": "offshore", "ok": True}
    dashboard = client.get("/offshore", headers=_h("admin"))
    assert dashboard.status_code == 200
    settings = client.get("/offshore/settings", headers=_h("admin"))
    assert settings.status_code == 200


def test_offshore_dashboard_tenant_override_and_i18n_sv_no_en():
    app = _mk_app()
    site_id = _seed_site(app)
    with app.app_context():
        db = get_session()
        try:
            db.add(TenantFeatureFlag(tenant_id=1, name="offshore.v2.enabled", enabled=True))
            db.commit()
        finally:
            db.close()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["tenant_id"] = 1
        sess["user_id"] = 99
        sess["role"] = "admin"
        sess["full_name"] = "Henrik"

    for lang, expected in [("sv", "Ingen aktiv arbetsperiod"), ("no", "Ingen aktiv arbeidsperiode"), ("en", "No active work period")]:
        r = client.get(f"/offshore?lang={lang}", headers=_h("admin"))
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "Offshore" in html
        assert expected in html
        assert "Menyimport" not in html
        assert "Inställningar" in html or "Innstillinger" in html or "Settings" in html

    unknown = client.get("/offshore?lang=zz", headers=_h("admin"))
    assert unknown.status_code == 200
    assert "Ingen aktiv arbetsperiod" in unknown.get_data(as_text=True)


def test_offshore_site_override_and_settings_access():
    app = _mk_app()
    site_id = _seed_site(app)
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("CREATE TABLE IF NOT EXISTS site_feature_flags(site_id TEXT NOT NULL, name TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0)"))
            db.execute(
                text("INSERT INTO site_feature_flags(site_id, name, enabled) VALUES(:sid, 'offshore.v2.enabled', 1)"),
                {"sid": site_id},
            )
            db.commit()
        finally:
            db.close()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["tenant_id"] = 1
        sess["user_id"] = 99
        sess["role"] = "admin"
        sess["full_name"] = "Henrik"

    r = client.get("/offshore/settings", headers=_h("admin"))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Arbetspositioner" in html or "Work positions" in html
    assert "Namn" in html or "Name" in html
    assert "Menycykel" in html


def test_offshore_viewer_gets_dashboard_but_not_settings():
    app = _mk_app()
    site_id = _seed_site(app)
    with app.app_context():
        db = get_session()
        try:
            db.add(TenantFeatureFlag(tenant_id=1, name="offshore.v2.enabled", enabled=True))
            db.commit()
        finally:
            db.close()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
        sess["tenant_id"] = 1
        sess["user_id"] = 101
        sess["role"] = "viewer"
        sess["full_name"] = "Viewer"

    dashboard = client.get("/offshore", headers=_h("viewer"))
    assert dashboard.status_code == 200
    settings = client.get("/offshore/settings", headers=_h("viewer"))
    assert settings.status_code == 403


def test_offshore_wrong_site_and_missing_site_handling():
    app = _mk_app()
    site_a = _seed_site(app, site_name="Site A")
    site_b = _seed_site(app, site_name="Site B")
    with app.app_context():
        db = get_session()
        try:
            db.add(TenantFeatureFlag(tenant_id=1, name="offshore.v2.enabled", enabled=True))
            db.commit()
        finally:
            db.close()
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["site_id"] = site_a
        sess["tenant_id"] = 1
        sess["user_id"] = 99
        sess["role"] = "admin"
    r = client.get(f"/offshore?site_id={site_b}", headers=_h("admin"))
    assert r.status_code == 403

    client2 = app.test_client()
    with client2.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 99
        sess["role"] = "admin"
    r2 = client2.get("/offshore", headers=_h("admin"))
    assert r2.status_code in (302, 303)
    assert "/ui/select-site" in r2.headers.get("Location", "")
