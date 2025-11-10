from __future__ import annotations

import re

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


class TestAdminPhaseB:
    def test_create_and_update_department_with_etag_and_sqlite_fallback(self):
        app = _mk_app()
        c = app.test_client()
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

        # Create site
        r = c.post("/admin/sites", headers=headers, json={"name": "North"})
        assert r.status_code == 201
        site = r.get_json()
        site_etag = r.headers.get("ETag")
        assert site_etag and site_etag.startswith('W/"admin:site:')

        # Create department
        r = c.post(
            "/admin/departments",
            headers=headers,
            json={"site_id": site["id"], "name": "Ward A", "resident_count_mode": "fixed", "resident_count_fixed": 10},
        )
        assert r.status_code == 201
        dept = r.get_json()
        etag = r.headers["ETag"]
        assert re.match(r'W/"admin:dept:[^"]+:v0"', etag)

        # Update department name with correct If-Match
        r = c.put(
            f"/admin/departments/{dept['id']}",
            headers={**headers, "If-Match": etag},
            json={"name": "Ward A1"},
        )
        assert r.status_code == 200
        etag2 = r.headers.get("ETag")
        assert etag2 and etag2 != etag

        # Retry with stale ETag → 412
        r = c.put(
            f"/admin/departments/{dept['id']}",
            headers={**headers, "If-Match": etag},
            json={"name": "Ward A2"},
        )
        assert r.status_code == 412

    def test_diet_defaults_validation_and_idempotency(self):
        app = _mk_app()
        c = app.test_client()
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

        # Create site + dept
        s = c.post("/admin/sites", headers=headers, json={"name": "East"}).get_json()
        d = c.post(
            "/admin/departments",
            headers=headers,
            json={"site_id": s["id"], "name": "Ward B", "resident_count_mode": "per_day_meal"},
        )
        dept = d.get_json()
        etag = d.headers["ETag"]

        # Negative count → 400
        r = c.put(
            f"/admin/departments/{dept['id']}/diet-defaults",
            headers={**headers, "If-Match": etag},
            json={"items": [{"diet_type_id": "veg", "default_count": -1}]},
        )
        assert r.status_code == 400

        # Valid upsert
        r = c.put(
            f"/admin/departments/{dept['id']}/diet-defaults",
            headers={**headers, "If-Match": etag},
            json={"items": [{"diet_type_id": "veg", "default_count": 3}]},
        )
        assert r.status_code == 200
        etag2 = r.headers["ETag"]
        # Repeat same payload → idempotent (ETag may or may not change depending on impl; response stays 200)
        r = c.put(
            f"/admin/departments/{dept['id']}/diet-defaults",
            headers={**headers, "If-Match": etag2},
            json={"items": [{"diet_type_id": "veg", "default_count": 3}]},
        )
        assert r.status_code == 200

        # Bump in background (simulate change) then expect 412 on stale If-Match
        stale = r.headers["ETag"]
        r2 = c.put(
            f"/admin/departments/{dept['id']}/diet-defaults",
            headers={**headers, "If-Match": stale},
            json={"items": [{"diet_type_id": "veg", "default_count": 4}]},
        )
        assert r2.status_code == 200
        # Now try using old stale again → 412
        r3 = c.put(
            f"/admin/departments/{dept['id']}/diet-defaults",
            headers={**headers, "If-Match": stale},
            json={"items": [{"diet_type_id": "veg", "default_count": 5}]},
        )
        assert r3.status_code == 412

    def test_rbac_and_ff(self):
        app = _mk_app()
        c = app.test_client()
        # viewer forbidden
        r = c.post("/admin/sites", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"}, json={"name": "N"})
        assert r.status_code == 403
        # feature flag off → 404
        reg = getattr(app, "feature_registry")
        reg.set("ff.admin.enabled", False)
        r = c.get("/admin/stats", headers={"X-User-Role": "editor", "X-Tenant-Id": "1"})
        assert r.status_code == 404

    def test_openapi_includes_if_match_and_etag_headers(self):
        app = _mk_app()
        c = app.test_client()
        r = c.get("/openapi.json")
        assert r.status_code == 200
        spec = r.get_json()
        # Check presence on update endpoints
        upd = spec["paths"]["/api/admin/departments/{id}"]["put"]
        hdrs = upd["parameters"]
        assert any(h["name"] == "If-Match" for h in hdrs)
        # Alt2 headers present
        alt2 = spec["paths"]["/api/admin/alt2"]["put"]
        assert any(p["name"] == "If-Match" for p in alt2["parameters"])

    def test_alt2_bulk_idempotent_and_collection_etag(self):
        app = _mk_app()
        c = app.test_client()
        headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
        # Create site+dept
        s = c.post("/admin/sites", headers=headers, json={"name": "West"}).get_json()
        d = c.post(
            "/admin/departments",
            headers=headers,
            json={"site_id": s["id"], "name": "Ward C", "resident_count_mode": "fixed", "resident_count_fixed": 5},
        ).get_json()
        # First bulk
        if_match = 'W/"admin:alt2:week:51:v0"'
        body = {"week": 51, "items": [{"department_id": d["id"], "weekday": 1, "enabled": True}, {"department_id": d["id"], "weekday": 3, "enabled": True}]}
        r = c.put("/admin/alt2", headers={**headers, "If-Match": if_match}, json=body)
        assert r.status_code == 200
        etag = r.headers.get("ETag")
        assert etag and etag.startswith('W/"admin:alt2:week:51:')
        # Second bulk same payload → idempotent 200, ETag should not regress
        r2 = c.put("/admin/alt2", headers={**headers, "If-Match": etag}, json=body)
        assert r2.status_code == 200
        etag2 = r2.headers.get("ETag")
        assert etag2 == etag, "Collection ETag must remain stable on identical payload"

        # Toggle one weekday enabled state → expect ETag change
        body_toggle = {"week": 51, "items": [{"department_id": d["id"], "weekday": 1, "enabled": False}, {"department_id": d["id"], "weekday": 3, "enabled": True}]}
        r3 = c.put("/admin/alt2", headers={**headers, "If-Match": etag2}, json=body_toggle)
        assert r3.status_code == 200
        etag3 = r3.headers.get("ETag")
        assert etag3 != etag2, "Collection ETag must bump when at least one flag toggles"

    def test_rbac_non_admin_writes_forbidden(self):
        app = _mk_app()
        c = app.test_client()
        # Editor attempting site create
        r = c.post("/admin/sites", headers={"X-User-Role": "editor", "X-Tenant-Id": "1"}, json={"name": "Nope"})
        assert r.status_code == 403
        # Viewer attempting department create
        r = c.post("/admin/departments", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"}, json={"site_id": "x", "name": "D", "resident_count_mode": "fixed"})
        assert r.status_code == 403
        # Cook/staff style role (simulate 'unit_portal')
        r = c.post("/admin/sites", headers={"X-User-Role": "unit_portal", "X-Tenant-Id": "1"}, json={"name": "Nope"})
        assert r.status_code == 403
        # Alt2 bulk forbidden
        r = c.put("/admin/alt2", headers={"X-User-Role": "editor", "X-Tenant-Id": "1", "If-Match": 'W/"admin:alt2:week:10:v0"'}, json={"week": 10, "items": []})
        assert r.status_code == 403
