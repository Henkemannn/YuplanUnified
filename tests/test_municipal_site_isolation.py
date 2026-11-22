from __future__ import annotations

from sqlalchemy import text

from core.db import get_new_session


SITE_A = "municipal-site-a"
SITE_B = "municipal-site-b"
SITE_OTHER_TENANT = "municipal-site-other-tenant"


def _seed_municipal_data(app) -> None:
    with app.app_context():
        db = get_new_session()
        try:
            db.execute(
                text(
                    "DELETE FROM dishes WHERE name IN "
                    "('Same Site Dish', 'Other Site Dish', "
                    "'Other Tenant Dish', 'Historical Dish')"
                )
            )
            db.execute(
                text(
                    "INSERT OR IGNORE INTO tenants(id, name, active) "
                    "VALUES (9901, 'Municipal Other Tenant', 1)"
                )
            )
            db.execute(
                text(
                    "INSERT OR IGNORE INTO sites(id, name, tenant_id) VALUES "
                    "(:site_a, 'Municipal A', 1), "
                    "(:site_b, 'Municipal B', 1), "
                    "(:other, 'Municipal Other', 9901)"
                ),
                {
                    "site_a": SITE_A,
                    "site_b": SITE_B,
                    "other": SITE_OTHER_TENANT,
                },
            )
            db.execute(
                text(
                    "INSERT INTO dishes(tenant_id, site_id, name, category) "
                    "VALUES "
                    "(1, :site_a, 'Same Site Dish', 'main'), "
                    "(1, :site_b, 'Other Site Dish', 'main'), "
                    "(9901, :other, 'Other Tenant Dish', 'main'), "
                    "(1, NULL, 'Historical Dish', 'main')"
                ),
                {
                    "site_a": SITE_A,
                    "site_b": SITE_B,
                    "other": SITE_OTHER_TENANT,
                },
            )
            db.commit()
        finally:
            db.close()


def _login(client, *, site_id: str | None, tenant_id: int = 1) -> None:
    client.environ_base = {"HTTP_X_USER_ROLE": "admin"}
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["role"] = "admin"
        session["tenant_id"] = tenant_id
        if site_id is None:
            session.pop("site_id", None)
        else:
            session["site_id"] = site_id


def _dish_id(site_id: str | None, tenant_id: int = 1) -> int:
    db = get_new_session()
    try:
        query = "SELECT id FROM dishes WHERE tenant_id=:tenant_id AND "
        params = {"tenant_id": tenant_id}
        if site_id is None:
            query += "site_id IS NULL AND name='Historical Dish'"
        else:
            query += "site_id=:site_id"
            params["site_id"] = site_id
        return int(db.execute(text(query), params).scalar_one())
    finally:
        db.close()


def test_municipal_variant_allows_same_site_dish_and_ignores_request_id(app_session):
    _seed_municipal_data(app_session)
    client = app_session.test_client()
    _login(client, site_id=SITE_A)

    response = client.post(
        "/municipal/menu/variant",
        json={
            "week": 30,
            "year": 2035,
            "day": "monday",
            "meal": "lunch",
            "variant_type": "main",
            "dish_id": _dish_id(SITE_A),
        },
        headers={"X-Request-ID": SITE_B},
    )

    assert response.status_code == 200


def test_municipal_variant_denies_cross_site_and_does_not_write(app_session):
    _seed_municipal_data(app_session)
    client = app_session.test_client()
    _login(client, site_id=SITE_A)

    response = client.post(
        "/municipal/menu/variant",
        json={
            "week": 31,
            "year": 2035,
            "day": "monday",
            "meal": "lunch",
            "variant_type": "main",
            "dish_id": _dish_id(SITE_B),
        },
    )

    assert response.status_code == 403
    with app_session.app_context():
        db = get_new_session()
        try:
            assert db.execute(
                text(
                    "SELECT COUNT(*) FROM menus "
                    "WHERE tenant_id=1 AND site_id=:site_id AND year=2035 AND week=31"
                ),
                {"site_id": SITE_A},
            ).scalar_one() == 0
        finally:
            db.close()


def test_municipal_variant_denies_cross_tenant_and_null_site_dishes(app_session):
    _seed_municipal_data(app_session)
    client = app_session.test_client()
    _login(client, site_id=SITE_A)

    for dish_id in (_dish_id(SITE_OTHER_TENANT, 9901), _dish_id(None)):
        response = client.post(
            "/municipal/menu/variant",
            json={
                "week": 32,
                "year": 2035,
                "day": "monday",
                "meal": "lunch",
                "variant_type": "main",
                "dish_id": dish_id,
            },
        )
        assert response.status_code == 403


def test_municipal_variant_requires_site_binding(app_session):
    _seed_municipal_data(app_session)
    client = app_session.test_client()
    _login(client, site_id=None)

    response = client.post(
        "/municipal/menu/variant",
        json={
            "week": 33,
            "year": 2035,
            "day": "monday",
            "meal": "lunch",
            "variant_type": "main",
            "dish_id": _dish_id(SITE_A),
        },
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "site_binding_required"
