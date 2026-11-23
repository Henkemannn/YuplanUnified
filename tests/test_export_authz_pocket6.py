"""Export API authz tests (P6.3 PR C)."""

from werkzeug.security import generate_password_hash

from core.admin_user_repo import _set_user_site_binding
from core.db import get_session
from core.models import User


def _login_role(client, role: str) -> None:
    with client.session_transaction() as sess:
        site_id = str(sess["site_id"])
    db = get_session()
    try:
        email = f"export-{role}@example.test"
        user = db.query(User).filter_by(email=email).first()
        if user is None:
            user = User(
                tenant_id=1,
                email=email,
                password_hash=generate_password_hash("pw"),
                role=role,
                unit_id=None,
            )
            db.add(user)
            db.flush()
        _set_user_site_binding(db, user_id=int(user.id), tenant_id=1, site_id=site_id)
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
    response = client.post("/auth/login", json={"email": email, "password": "pw"})
    assert response.status_code == 200


def test_export_unauthorized_no_session(client_no_tenant):
    r = client_no_tenant.get("/export/notes.csv")
    assert r.status_code == 401
    body = r.get_data(as_text=True)  # CSV endpoints return JSON error envelope via handler
    assert '"status":401' in body and "/unauthorized" in body


def test_export_forbidden_viewer(client_admin):
    # viewer (canonical) should not export (requires editor or admin)
    _login_role(client_admin, "viewer")
    r = client_admin.get("/export/notes.csv")
    assert r.status_code == 403
    txt = r.get_data(as_text=True)
    assert '"status":403' in txt and "/forbidden" in txt and '"required_role":"editor"' in txt


def test_export_happy_editor(client_admin):
    _login_role(client_admin, "editor")
    r = client_admin.get("/export/notes.csv")
    assert r.status_code == 200
    # Response is CSV; first header row expected
    head = r.data.decode().splitlines()[0]
    assert "id" in head and "content" in head
