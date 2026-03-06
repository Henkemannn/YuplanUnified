import re
import uuid

from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

from core.db import get_session


def _h(role: str, user_id: int) -> dict[str, str]:
    return {
        "X-User-Role": role,
        "X-Tenant-Id": "1",
        "X-User-Id": str(user_id),
    }


def _extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else ""


def _seed_site(site_id: str, name: str = "Account Test Site") -> None:
    db = get_session()
    try:
        db.execute(
            text("INSERT INTO sites (id, name, tenant_id, version) VALUES (:id, :name, 1, 0)"),
            {"id": site_id, "name": name},
        )
        db.commit()
    finally:
        db.close()


def _seed_user(*, role: str, email: str, password: str, full_name: str, site_id: str | None = None) -> int:
    db = get_session()
    try:
        cols = db.execute(text("PRAGMA table_info(users)")).fetchall()
        has_site_id = any(str(c[1]) == "site_id" for c in cols)
        if has_site_id:
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active, site_id) "
                    "VALUES (1, :email, :ph, :role, :username, :full_name, 1, :site_id)"
                ),
                {
                    "email": email,
                    "ph": generate_password_hash(password),
                    "role": role,
                    "username": email,
                    "full_name": full_name,
                    "site_id": site_id,
                },
            )
        else:
            db.execute(
                text(
                    "INSERT INTO users (tenant_id, email, password_hash, role, username, full_name, is_active) "
                    "VALUES (1, :email, :ph, :role, :username, :full_name, 1)"
                ),
                {
                    "email": email,
                    "ph": generate_password_hash(password),
                    "role": role,
                    "username": email,
                    "full_name": full_name,
                },
            )
        db.commit()
        row = db.execute(text("SELECT id FROM users WHERE email=:email LIMIT 1"), {"email": email}).fetchone()
        assert row is not None
        user_id = int(row[0])
        if role == "kitchen" and site_id and not has_site_id:
            db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                    "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) VALUES (:uid, 1, :sid) "
                    "ON CONFLICT(user_id) DO UPDATE SET site_id=excluded.site_id"
                ),
                {"uid": user_id, "sid": site_id},
            )
            db.commit()
        return user_id
    finally:
        db.close()


def _bind_session(client, *, user_id: int, role: str, site_id: str):
    with client.session_transaction() as sess:
        sess["user_id"] = int(user_id)
        sess["role"] = role
        sess["tenant_id"] = 1
        sess["site_id"] = site_id


def test_account_page_loads_for_admin(client_admin):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    user_id = _seed_user(
        role="admin",
        email="admin.account@example.com",
        password="old-pass-123",
        full_name="Admin Account",
        site_id=site_id,
    )
    _bind_session(client_admin, user_id=user_id, role="admin", site_id=site_id)

    resp = client_admin.get("/ui/account", headers=_h("admin", user_id))

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Mitt konto" in html
    assert "admin.account@example.com" in html


def test_account_page_loads_for_kitchen(client_user):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    user_id = _seed_user(
        role="kitchen",
        email="kitchen.account@example.com",
        password="old-pass-123",
        full_name="Kitchen Account",
        site_id=site_id,
    )
    _bind_session(client_user, user_id=user_id, role="kitchen", site_id=site_id)

    resp = client_user.get("/ui/account", headers=_h("kitchen", user_id))

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Mitt konto" in html
    assert "kitchen.account@example.com" in html


def test_account_password_change_success(client_admin):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    user_id = _seed_user(
        role="admin",
        email="admin.change@example.com",
        password="old-pass-123",
        full_name="Admin Change",
        site_id=site_id,
    )
    _bind_session(client_admin, user_id=user_id, role="admin", site_id=site_id)

    pre = client_admin.get("/ui/account", headers=_h("admin", user_id))
    csrf = _extract_csrf(pre.data.decode("utf-8"))

    resp = client_admin.post(
        "/ui/account/password",
        headers=_h("admin", user_id),
        data={
            "current_password": "old-pass-123",
            "new_password": "new-pass-456",
            "confirm_password": "new-pass-456",
            "csrf_token": csrf,
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Lösenord uppdaterat." in resp.data.decode("utf-8")

    db = get_session()
    try:
        row = db.execute(text("SELECT password_hash FROM users WHERE id=:uid"), {"uid": user_id}).fetchone()
        assert row is not None
        assert check_password_hash(str(row[0]), "new-pass-456")
    finally:
        db.close()


def test_account_password_change_rejects_wrong_current_password(client_admin):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    user_id = _seed_user(
        role="admin",
        email="admin.wrong-current@example.com",
        password="old-pass-123",
        full_name="Admin Wrong Current",
        site_id=site_id,
    )
    _bind_session(client_admin, user_id=user_id, role="admin", site_id=site_id)

    pre = client_admin.get("/ui/account", headers=_h("admin", user_id))
    csrf = _extract_csrf(pre.data.decode("utf-8"))

    resp = client_admin.post(
        "/ui/account/password",
        headers=_h("admin", user_id),
        data={
            "current_password": "definitely-wrong",
            "new_password": "new-pass-456",
            "confirm_password": "new-pass-456",
            "csrf_token": csrf,
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Nuvarande lösenord är felaktigt." in resp.data.decode("utf-8")

    db = get_session()
    try:
        row = db.execute(text("SELECT password_hash FROM users WHERE id=:uid"), {"uid": user_id}).fetchone()
        assert row is not None
        assert check_password_hash(str(row[0]), "old-pass-123")
        assert not check_password_hash(str(row[0]), "new-pass-456")
    finally:
        db.close()


def test_account_password_change_rejects_mismatched_confirmation(client_admin):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    user_id = _seed_user(
        role="admin",
        email="admin.mismatch@example.com",
        password="old-pass-123",
        full_name="Admin Mismatch",
        site_id=site_id,
    )
    _bind_session(client_admin, user_id=user_id, role="admin", site_id=site_id)

    pre = client_admin.get("/ui/account", headers=_h("admin", user_id))
    csrf = _extract_csrf(pre.data.decode("utf-8"))

    resp = client_admin.post(
        "/ui/account/password",
        headers=_h("admin", user_id),
        data={
            "current_password": "old-pass-123",
            "new_password": "new-pass-456",
            "confirm_password": "different-pass-999",
            "csrf_token": csrf,
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert "Nytt lösenord och bekräftelse matchar inte." in resp.data.decode("utf-8")

    db = get_session()
    try:
        row = db.execute(text("SELECT password_hash FROM users WHERE id=:uid"), {"uid": user_id}).fetchone()
        assert row is not None
        assert check_password_hash(str(row[0]), "old-pass-123")
        assert not check_password_hash(str(row[0]), "new-pass-456")
    finally:
        db.close()


def test_logout_from_ui_clears_session(client_admin):
    site_id = f"site-{uuid.uuid4()}"
    _seed_site(site_id)
    user_id = _seed_user(
        role="admin",
        email="admin.logout@example.com",
        password="old-pass-123",
        full_name="Admin Logout",
        site_id=site_id,
    )
    _bind_session(client_admin, user_id=user_id, role="admin", site_id=site_id)

    pre = client_admin.get("/ui/account", headers=_h("admin", user_id))
    csrf = _extract_csrf(pre.data.decode("utf-8"))

    resp = client_admin.post(
        "/ui/logout",
        headers=_h("admin", user_id),
        data={"csrf_token": csrf},
        follow_redirects=False,
    )

    assert resp.status_code in (301, 302)
    assert "/ui/login" in (resp.headers.get("Location") or "")

    with client_admin.session_transaction() as sess:
        assert sess.get("user_id") is None
        assert sess.get("role") is None
