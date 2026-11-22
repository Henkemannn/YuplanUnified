import uuid

from werkzeug.security import generate_password_hash
from sqlalchemy import text

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, User


def _bootstrap(db):
    t = Tenant(name="MenuT_" + uuid.uuid4().hex[:6])
    db.add(t)
    db.flush()
    u = User(
        tenant_id=t.id,
        email=f"cook_{uuid.uuid4().hex[:6]}@ex.com",
        password_hash=generate_password_hash("pw"),
        role="cook",
        unit_id=None,
    )
    db.add(u)
    db.flush()
    site_id = f"site-{uuid.uuid4().hex[:8]}"
    db.execute(
        text(
            """
            INSERT INTO sites (id, name, tenant_id, version)
            VALUES (:id, :name, :tenant_id, 0)
            """
        ),
        {"id": site_id, "name": "Menu Variant Site", "tenant_id": int(t.id)},
    )
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS kitchen_user_sites (
                user_id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                site_id TEXT NOT NULL
            )
            """
        )
    )
    db.execute(
        text(
            """
            INSERT OR REPLACE INTO kitchen_user_sites (user_id, tenant_id, site_id)
            VALUES (:user_id, :tenant_id, :site_id)
            """
        ),
        {"user_id": int(u.id), "tenant_id": int(t.id), "site_id": site_id},
    )
    db.commit()
    return t, u, site_id


def _login(client, email, site_id):
    # Bind session to a test site to satisfy strict policy
    with client.session_transaction() as sess:
        sess["site_id"] = str(site_id)
    r = client.post("/auth/login", json={"email": email, "password": "pw"})
    assert r.status_code == 200


def test_menu_variant_set_and_week_view():
    app = create_app({"TESTING": True, "SECRET_KEY": "x"})
    client = app.test_client()
    db = get_session()
    t, u, site_id = _bootstrap(db)
    user_email = u.email
    db.close()

    _login(client, user_email, site_id)

    payload = {
        "week": 40,
        "year": 2025,
        "day": "Mon",
        "meal": "Lunch",
        "variant_type": "alt1",
        "dish_name": "Pasta Bolognese",
    }
    r = client.post("/menu/variant/set", json=payload)
    assert r.status_code == 200
    mv_id = r.get_json()["menu_variant_id"]
    assert mv_id is not None

    # Set second variant referencing same dish by name again (idempotent dish creation)
    payload2 = {
        "week": 40,
        "year": 2025,
        "day": "Mon",
        "meal": "Lunch",
        "variant_type": "dessert",
        "dish_name": "Pasta Bolognese",
    }
    r2 = client.post("/menu/variant/set", json=payload2)
    assert r2.status_code == 200

    # Retrieve week
    week_resp = client.get("/menu/week", query_string={"week": 40, "year": 2025})
    assert week_resp.status_code == 200
    data = week_resp.get_json()
    assert data["ok"] is True
    days = data["menu"]["days"]
    assert "Mon" in days
    lunch = days["Mon"]["Lunch"]
    assert lunch["alt1"]["dish_name"] == "Pasta Bolognese"
    assert lunch["dessert"]["dish_name"] == "Pasta Bolognese"

    # Update alt1 variant to a different dish name (new dish)
    r3 = client.post("/menu/variant/set", json={**payload, "dish_name": "Fish Pie"})
    assert r3.status_code == 200
    week_resp2 = client.get("/menu/week", query_string={"week": 40, "year": 2025})
    lunch2 = week_resp2.get_json()["menu"]["days"]["Mon"]["Lunch"]
    assert lunch2["alt1"]["dish_name"] == "Fish Pie"
    # Dessert unchanged
    assert lunch2["dessert"]["dish_name"] == "Pasta Bolognese"


def test_menu_week_allows_kitchen_role(client):
    from core.db import get_session
    from sqlalchemy import text
    import uuid

    site_id = f"site-{uuid.uuid4().hex[:8]}"
    db = get_session()
    try:
        user = User(
            tenant_id=1,
            email=f"kitchen_{uuid.uuid4().hex[:6]}@ex.com",
            password_hash=generate_password_hash("pw"),
            role="kitchen",
        )
        db.add(user)
        db.flush()
        db.execute(
            text("INSERT INTO sites (id, name, tenant_id, version) VALUES (:id, :name, 1, 0)"),
            {"id": site_id, "name": "Kitchen Site"},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO kitchen_user_sites "
                "(user_id, tenant_id, site_id) VALUES (:user_id, 1, :site_id)"
            ),
            {"user_id": int(user.id), "site_id": site_id},
        )
        user_id = int(user.id)
        db.commit()
    finally:
        db.close()

    with client.session_transaction() as sess:
        sess.update(
            {"site_id": site_id, "tenant_id": 1, "user_id": user_id, "role": "kitchen"}
        )

    resp = client.get(
        "/menu/week",
        query_string={"week": 10, "year": 2026, "site_id": site_id},
        headers={
            "X-User-Role": "kitchen",
            "X-Tenant-Id": "1",
            "X-User-Id": str(user_id),
        },
    )

    assert resp.status_code == 200
    body = resp.get_json() or {}
    assert body.get("ok") is True


def test_menu_week_requires_current_site_binding(app_session):
    app = app_session
    client = app.test_client()
    db = get_session()
    tenant, user, site_a = _bootstrap(db)
    tenant_id = int(tenant.id)
    user_id = int(user.id)
    site_b = f"site-{uuid.uuid4().hex[:8]}"
    other_tenant = Tenant(name="OtherMenuT_" + uuid.uuid4().hex[:6])
    db.add(other_tenant)
    db.flush()
    other_site = f"site-{uuid.uuid4().hex[:8]}"
    db.execute(
        text(
            "INSERT INTO sites (id, name, tenant_id, version) VALUES "
            "(:site_b, 'Menu B', :tenant_id, 0), "
            "(:other_site, 'Other tenant site', :other_tenant, 0)"
        ),
        {
            "site_b": site_b,
            "other_site": other_site,
            "tenant_id": tenant_id,
            "other_tenant": int(other_tenant.id),
        },
    )
    db.commit()
    db.close()

    with client.session_transaction() as sess:
        sess.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "role": "cook",
                "site_id": site_a,
            }
        )
    auth_headers = {
        "X-User-Role": "cook",
        "X-Tenant-Id": str(tenant_id),
        "X-User-Id": str(user_id),
    }

    own = client.get(
        "/menu/week",
        query_string={"site_id": site_a, "week": 41, "year": 2025},
        headers=auth_headers,
    )
    assert own.status_code == 200

    same_tenant_foreign = client.get(
        "/menu/week",
        query_string={"site_id": site_b, "week": 41, "year": 2025},
        headers=auth_headers,
    )
    assert same_tenant_foreign.status_code == 403

    cross_tenant_foreign = client.get(
        "/menu/week",
        query_string={"site_id": other_site, "week": 41, "year": 2025},
        headers=auth_headers,
    )
    assert cross_tenant_foreign.status_code == 403

    db = get_session()
    try:
        db.execute(
            text(
                "DELETE FROM kitchen_user_sites "
                "WHERE user_id=:user_id"
            ),
            {"user_id": user_id},
        )
        db.commit()
    finally:
        db.close()
    revoked = client.get(
        "/menu/week",
        query_string={"site_id": site_a, "week": 41, "year": 2025},
        headers=auth_headers,
    )
    assert revoked.status_code == 403
