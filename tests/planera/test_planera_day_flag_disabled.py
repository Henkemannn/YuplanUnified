import uuid
from datetime import date


def _h(role):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def test_planera_day_flag_disabled_returns_404(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    d = date(2025, 11, 21).isoformat()

    from core.db import create_all, get_session
    from sqlalchemy import text
    import os
    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:i,:n,0)"), {"i": site_id, "n": "SiteX"})
            db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) VALUES(:i,:s,:n,'fixed',0,0)"), {"i": dep_id, "s": site_id, "n": "AvdX"})
            db.commit()
        finally:
            db.close()
        # Ensure feature flag NOT added => disabled
        reg = getattr(app, "feature_registry", None)
        if reg and reg.has("ff.planera.enabled"):
            reg.set("ff.planera.enabled", False)

    r_api = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))
    assert r_api.status_code == 404

    r_ui = client_admin.get(f"/ui/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))
    assert r_ui.status_code == 404
