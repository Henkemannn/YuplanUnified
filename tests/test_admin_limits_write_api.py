from core.app_factory import create_app


def _app():
    return create_app({"TESTING": True})


def test_limits_write_unauthorized():
    c = _app().test_client()
    rv = c.post("/admin/limits", json={})
    assert rv.status_code == 401


def test_limits_write_forbidden_viewer():
    c = _app().test_client()
    rv = c.post(
        "/admin/limits",
        headers={"X-User-Role": "viewer"},
        json={"tenant_id": 1, "name": "x", "quota": 5, "per_seconds": 60},
    )
    assert rv.status_code == 403


def test_limits_create_and_update_cycle():
    c = _app().test_client()
    # create
    rv = c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 1, "name": "exp", "quota": 10, "per_seconds": 60},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["ok"] and data["item"]["source"] == "tenant"
    # update (change quota -> 20)
    rv2 = c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 1, "name": "exp", "quota": 20, "per_seconds": 60},
    )
    data2 = rv2.get_json()
    assert rv2.status_code == 200 and data2["updated"] is True and data2["item"]["quota"] == 20


def test_limits_delete_idempotent():
    c = _app().test_client()
    # create first
    c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 2, "name": "exp", "quota": 5, "per_seconds": 60},
    )
    # delete
    rv = c.delete(
        "/admin/limits", headers={"X-User-Role": "admin"}, json={"tenant_id": 2, "name": "exp"}
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["removed"] is True
    # delete again
    rv2 = c.delete(
        "/admin/limits", headers={"X-User-Role": "admin"}, json={"tenant_id": 2, "name": "exp"}
    )
    assert rv2.status_code == 200
    data2 = rv2.get_json()
    assert data2["removed"] is False


def test_limits_invalid_payload():
    c = _app().test_client()
    rv = c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 1, "name": "exp", "quota": "abc", "per_seconds": 60},
    )
    assert rv.status_code == 400
    rv2 = c.post(
        "/admin/limits", headers={"X-User-Role": "admin"}, json={"tenant_id": 1, "name": "exp"}
    )
    assert rv2.status_code == 400


def test_limits_clamp():
    c = _app().test_client()
    rv = c.post(
        "/admin/limits",
        headers={"X-User-Role": "admin"},
        json={"tenant_id": 1, "name": "clamp", "quota": 0, "per_seconds": 1000000},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    # quota should clamp to 1, per_seconds to 86400
    assert data["item"]["quota"] == 1
    assert data["item"]["per_seconds"] == 86400
