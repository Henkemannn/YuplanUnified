from __future__ import annotations

from core.app_factory import create_app
from core.db import create_all


def _enable_flag(app, name: str, enabled: bool = True):
    reg = getattr(app, "feature_registry", None)
    assert reg is not None
    if not reg.has(name):
        reg.add(name)
    reg.set(name, enabled)


def _mk_app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with app.app_context():
        create_all()
    _enable_flag(app, "ff.admin.enabled", True)
    return app


class TestAdminPhaseDConditionalGET:
    def test_sites_200_then_304(self):
        app = _mk_app()
        c = app.test_client()
        headers = {"X-User-Role": "editor", "X-Tenant-Id": "1"}
        # Create one site via admin (requires admin role)
        c.post("/admin/sites", headers={**headers, "X-User-Role": "admin"}, json={"name": "S1"})
        r1 = c.get("/admin/sites", headers=headers)
        assert r1.status_code == 200
        etag = r1.headers.get("ETag")
        assert etag and etag.startswith('W/"admin:sites:')
        r2 = c.get("/admin/sites", headers={**headers, "If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.headers.get("ETag") == etag

    def test_departments_collection_200_then_304(self):
        app = _mk_app()
        c = app.test_client()
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        s = c.post("/admin/sites", headers=headers, json={"name": "North"}).get_json()
        c.post("/admin/departments", headers=headers, json={"site_id": s["id"], "name": "Ward A", "resident_count_mode": "fixed", "resident_count_fixed": 10})
        r1 = c.get(f"/admin/departments?site={s['id']}", headers=headers)
        assert r1.status_code == 200
        et = r1.headers.get("ETag")
        assert et and et.startswith('W/"admin:departments:site:')
        r2 = c.get(f"/admin/departments?site={s['id']}", headers={**headers, "If-None-Match": et})
        assert r2.status_code == 304
        assert r2.headers.get("ETag") == et

    def test_diet_defaults_single_200_then_304_then_bump(self):
        app = _mk_app()
        c = app.test_client()
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        s = c.post("/admin/sites", headers=headers, json={"name": "East"}).get_json()
        d = c.post("/admin/departments", headers=headers, json={"site_id": s["id"], "name": "Ward B", "resident_count_mode": "fixed", "resident_count_fixed": 5}).get_json()
        r1 = c.get(f"/admin/diet-defaults?department={d['id']}", headers=headers)
        assert r1.status_code == 200
        et = r1.headers.get("ETag")
        assert et and et.startswith('W/"admin:dept:')
        r2 = c.get(f"/admin/diet-defaults?department={d['id']}", headers={**headers, "If-None-Match": et})
        assert r2.status_code == 304
        # Now write to bump version
        c.put(f"/admin/departments/{d['id']}", headers={**headers, "If-Match": et}, json={"name": "Ward B2"})
        r3 = c.get(f"/admin/diet-defaults?department={d['id']}", headers={**headers, "If-None-Match": et})
        assert r3.status_code == 200
        assert r3.headers.get("ETag") != et

    def test_alt2_collection_200_then_304(self):
        app = _mk_app()
        c = app.test_client()
        headers = {"X-User-Role": "editor", "X-Tenant-Id": "1"}
        # Seed a site for scope
        s = c.post("/admin/sites", headers={**headers, "X-User-Role": "admin"}, json={"name": "S1"}).get_json()
        r1 = c.get(f"/admin/alt2?week=12&site={s['id']}", headers=headers)
        assert r1.status_code == 200
        et = r1.headers.get("ETag")
        assert et and et.startswith('W/"admin:alt2:week:12:')
        r2 = c.get(f"/admin/alt2?week=12&site={s['id']}", headers={**headers, "If-None-Match": et})
        assert r2.status_code == 304

    def test_notes_department_200_then_304(self):
        app = _mk_app()
        c = app.test_client()
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        s = c.post("/admin/sites", headers=headers, json={"name": "N"}).get_json()
        d = c.post("/admin/departments", headers=headers, json={"site_id": s["id"], "name": "Dept", "resident_count_mode": "fixed", "resident_count_fixed": 0}).get_json()
        r1 = c.get(f"/admin/notes?scope=department&department_id={d['id']}", headers=headers)
        assert r1.status_code == 200
        et = r1.headers.get("ETag")
        assert et and et.startswith('W/"admin:dept:')
        r2 = c.get(f"/admin/notes?scope=department&department_id={d['id']}", headers={**headers, "If-None-Match": et})
        assert r2.status_code == 304
