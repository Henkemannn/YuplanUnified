from core.app_factory import create_app
from core.db import create_all


def test_select_site_forbidden_for_admin(client_admin, app_session):
    # Ensure schema exists for route rendering
    with app_session.app_context():
        create_all()
    # Admin should get 403 on GET /ui/select-site
    # Emulate logged-in admin session
    with client_admin.session_transaction() as sess:
        sess["user_id"] = "u-admin"
        sess["role"] = "admin"
        sess["tenant_id"] = 1
    r = client_admin.get("/ui/select-site")
    assert r.status_code == 403
    # POST is also forbidden
    r2 = client_admin.post("/ui/select-site", data={"site_id": "s1", "next": "/"})
    assert r2.status_code == 403
