import uuid


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_week_etag_304(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    year, week = 2025, 48

    from core.db import create_all, get_session
    from sqlalchemy import text
    import os
    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "SiteET"})
            db.commit()
        finally:
            db.close()
        reg = getattr(app, "feature_registry", None)
        if reg:
            if not reg.has("ff.planera.enabled"):
                reg.add("ff.planera.enabled")
            reg.set("ff.planera.enabled", True)

    r1 = client_admin.get(f"/api/planera/week?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag and etag.startswith('W/"planera:week:')

    r2 = client_admin.get(f"/api/planera/week?site_id={site_id}&year={year}&week={week}", headers={**_h("admin"), "If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.get_data(as_text=True) == ""
