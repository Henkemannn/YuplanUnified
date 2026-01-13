from flask import Flask

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Tenant


def _enable_flag(app: Flask, name: str, enabled: bool = True):
    # Ensure the feature flag exists, then set its state globally for tests
    reg = getattr(app, "feature_registry", None)
    assert reg is not None
    if not reg.has(name):
        reg.add(name)
    reg.set(name, enabled)


def _bootstrap_db(app: Flask):
    # Create schema and seed a tenant with id=1 if missing
    with app.app_context():
        create_all()
        db = get_session()
        try:
            if not db.query(Tenant).first():
                db.add(Tenant(name="TestTenant"))
                db.commit()
        finally:
            db.close()


def test_dashboard_requires_login_redirects_then_renders_after_login():
    app: Flask = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    _bootstrap_db(app)
    _enable_flag(app, "ff.dashboard.enabled", True)
    client = app.test_client()
    # Unauthenticated -> redirect (302) to landing/root
    r0 = client.get("/dashboard", follow_redirects=False)
    assert r0.status_code in (302, 303)
    # Now simulate login via testing headers (sets session in before_request)
    r1 = client.get("/dashboard", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r1.status_code == 200
    body = r1.data
    assert b"Dashboard" in body
    # Snapshot-relevant elements
    assert b"id=\"widget-today-menu\"" in body
    assert b"id=\"widget-quickstart\"" in body
    assert b"id=\"widget-alerts\"" in body
    assert b"id=\"widget-dept-notes\"" in body
    assert b"id=\"widget-tasks\"" in body
    assert b"id=\"widget-notes\"" in body
    assert b"id=\"widget-shortcuts\"" in body


def test_dashboard_rbac_forbidden_for_wrong_role():
    app: Flask = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    _bootstrap_db(app)
    _enable_flag(app, "ff.dashboard.enabled", True)
    client = app.test_client()
    r = client.get("/dashboard", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    assert r.status_code == 403


def test_dashboard_feature_flag_off_is_404():
    app: Flask = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    _bootstrap_db(app)
    _enable_flag(app, "ff.dashboard.enabled", False)
    client = app.test_client()
    r = client.get("/dashboard", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 404


def test_root_redirects_to_dashboard_when_logged_in():
    app: Flask = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    _bootstrap_db(app)
    _enable_flag(app, "ff.dashboard.enabled", True)
    client = app.test_client()
    r = client.get("/", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers.get("Location", "").endswith("/dashboard")


def test_quickstart_links_visible_for_admin_and_editor_as_staff_proxy():
    """Admin and 'editor' (proxy for staff) should see active quickstart links.

    Note: Until backend RBAC maps 'staff' explicitly, we treat 'editor' as staff-equivalent
    for template visibility. No backend logic changed per brief.
    """
    app: Flask = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    _bootstrap_db(app)
    _enable_flag(app, "ff.dashboard.enabled", True)
    client = app.test_client()

    # Admin
    r_admin = client.get("/dashboard", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r_admin.status_code == 200
    b1 = r_admin.data
    assert b'href="/weekview"' in b1
    assert b'href="/report"' in b1
    assert b'href="/planning"' in b1

    # Editor as staff proxy
    r_editor = client.get("/dashboard", headers={"X-User-Role": "editor", "X-Tenant-Id": "1"})
    assert r_editor.status_code == 200
    b2 = r_editor.data
    assert b'href="/weekview"' in b2
    assert b'href="/report"' in b2
    assert b'href="/planning"' in b2


def test_quickstart_links_disabled_for_viewer():
    app: Flask = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    _bootstrap_db(app)
    _enable_flag(app, "ff.dashboard.enabled", True)
    client = app.test_client()

    r = client.get("/dashboard", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    # viewer cannot access dashboard (RBAC), expect 403; skip link assertions in that case
    if r.status_code == 200:
        body = r.data
        # No hrefs for quickstart targets
        assert b'href="/weekview"' not in body
        assert b'href="/report"' not in body
        assert b'href="/planning"' not in body
        # Disabled buttons present with tooltip
        assert b'id="widget-quickstart"' in body
        assert b"disabled" in body
        assert b"Insufficient permissions" in body
    else:
        assert r.status_code == 403
