import uuid


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_week_flag_disabled_returns_404(client_admin):
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
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "SiteY"})
            db.commit()
        finally:
            db.close()
        reg = getattr(app, "feature_registry", None)
        if reg and reg.has("ff.planera.enabled"):
            reg.set("ff.planera.enabled", False)

    r_api = client_admin.get(f"/api/planera/week?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r_api.status_code == 404

    r_ui = client_admin.get(f"/ui/planera/week?site_id={site_id}&year={year}&week={week}", headers=_h("admin"))
    assert r_ui.status_code == 404
