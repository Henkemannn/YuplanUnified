import pytest
from werkzeug.security import generate_password_hash

from core.admin_user_repo import _set_user_site_binding
from core.db import get_session
from core.models import User


def _login_admin(client):
    with client.session_transaction() as sess:
        site_id = str(sess["site_id"])
    db = get_session()
    try:
        user = db.query(User).filter_by(email="weekview-parity-admin@example.test").first()
        if user is None:
            user = User(
                tenant_id=1,
                email="weekview-parity-admin@example.test",
                password_hash=generate_password_hash("pw"),
                role="admin",
                unit_id=None,
            )
            db.add(user)
            db.flush()
        _set_user_site_binding(db, user_id=int(user.id), tenant_id=1, site_id=site_id)
        db.commit()
    finally:
        db.close()
    response = client.post(
        "/auth/login",
        json={"email": "weekview-parity-admin@example.test", "password": "pw"},
    )
    assert response.status_code == 200
    return site_id


def test_weekview_report_ui_readonly_and_headers(client_admin):
    site_id = _login_admin(client_admin)
    r = client_admin.get(f"/ui/reports/weekview?site_id={site_id}&year=2025&week=47")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    # Assert presence of Swedish headers we standardised
    assert "Lunch" in html
    assert "Kväll" in html
    assert "Totalt" in html
    # No forms/write actions under reports
    assert "method=\"post\"" not in html.lower()


def test_weekview_report_endpoint_is_get_only(client_admin):
    # Ensure no POST/PUT/DELETE route exists for UI report path
    app = client_admin.application
    with app.app_context():
        methods = None
        for r in app.url_map.iter_rules():
            if str(r.rule).startswith("/ui/reports/weekview"):
                methods = r.methods
                break
        assert methods is not None
        assert methods == {"GET", "HEAD", "OPTIONS"}
