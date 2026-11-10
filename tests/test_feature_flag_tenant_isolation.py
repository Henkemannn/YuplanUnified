from sqlalchemy import text

from core.db import get_session
from core.models import Tenant


# Test-owned name: it must not collide with product flags or other tests.
FLAG_NAME = "ff.test.tenant_isolation_regression"


def _headers(role: str, tenant_id: int) -> dict[str, str]:
    return {
        "X-User-Role": role,
        "X-Tenant-Id": str(tenant_id),
    }


def test_feature_set_is_tenant_scoped_and_preserves_registry(app_session):
    app = app_session
    client = app.test_client()

    with app.app_context():
        db = get_session()
        try:
            if db.get(Tenant, 2) is None:
                db.add(Tenant(id=2, name="Tenant Two", active=True))
                db.commit()
            initial_rows = db.execute(
                text(
                    "SELECT tenant_id, enabled FROM tenant_feature_flags "
                    "WHERE name=:name ORDER BY tenant_id"
                ),
                {"name": FLAG_NAME},
            ).fetchall()
        finally:
            db.close()

        registry = app.feature_registry
        initial_registry = registry.list()

    assert initial_rows == []
    assert all(item["name"] != FLAG_NAME for item in initial_registry)

    enabled = client.post(
        "/features/set",
        json={"name": FLAG_NAME, "enabled": True},
        headers=_headers("admin", 2),
    )
    assert enabled.status_code == 200
    assert enabled.get_json() == {
        "ok": True,
        "name": FLAG_NAME,
        "enabled": True,
    }

    with app.app_context():
        db = get_session()
        try:
            rows = db.execute(
                text(
                    "SELECT tenant_id, enabled FROM tenant_feature_flags "
                    "WHERE name=:name ORDER BY tenant_id"
                ),
                {"name": FLAG_NAME},
            ).fetchall()
        finally:
            db.close()
        assert rows == [(2, 1)]
        assert app.feature_registry.list() == initial_registry
        assert app.feature_registry.enabled(FLAG_NAME) is False

    tenant_two = client.get(
        "/features/check",
        query_string={"name": FLAG_NAME},
        headers=_headers("admin", 2),
    )
    assert tenant_two.status_code == 200
    assert tenant_two.get_json()["enabled"] is True

    tenant_one = client.get(
        "/features/check",
        query_string={"name": FLAG_NAME},
        headers=_headers("admin", 1),
    )
    assert tenant_one.status_code == 200
    assert tenant_one.get_json()["enabled"] is False

    unauthorized = client.post(
        "/features/set",
        json={"name": FLAG_NAME, "enabled": False},
        headers=_headers("cook", 2),
    )
    assert unauthorized.status_code in (401, 403)

    disabled = client.post(
        "/features/set",
        json={"name": FLAG_NAME, "enabled": False},
        headers=_headers("admin", 2),
    )
    assert disabled.status_code == 200

    with app.app_context():
        db = get_session()
        try:
            rows = db.execute(
                text(
                    "SELECT tenant_id, enabled FROM tenant_feature_flags "
                    "WHERE name=:name ORDER BY tenant_id"
                ),
                {"name": FLAG_NAME},
            ).fetchall()
        finally:
            db.close()
        assert rows == [(2, 0)]
        assert app.feature_registry.list() == initial_registry
        assert app.feature_registry.enabled(FLAG_NAME) is False
