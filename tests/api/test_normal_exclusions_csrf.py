import os
from sqlalchemy import text

from core import create_app
from core.db import create_all


def _make_app(tmp_path):
    db_file = tmp_path / "csrf_test.db"
    url = f"sqlite:///{db_file}"
    # Enforce CSRF in tests to simulate production policy
    app = create_app({
        "TESTING": True,
        "STRICT_CSRF_IN_TESTS": True,
        "SECRET_KEY": "test",
        "database_url": url,
        "FORCE_DB_REINIT": True,
    })
    with app.app_context():
        create_all()
    return app


def _payload():
    return {
        "site_id": "site-csrf-1",
        "year": 2026,
        "week": 6,
        "day_index": 2,
        "meal": "lunch",
        "alt": "1",
        "diet_type_id": "dt1",
    }


def test_toggle_without_csrf_is_forbidden(tmp_path):
    app = _make_app(tmp_path)
    client = app.test_client()
    # Authenticate session to avoid 401 from require_roles
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "admin"
        sess["tenant_id"] = "1"
    r = client.post(
        "/api/kitchen/planering/normal_exclusions/toggle",
        json=_payload(),
        headers={"Origin": "http://evil.example"},  # force origin mismatch so CSRF evaluates
    )
    assert r.status_code == 403, r.get_data(as_text=True)


def test_toggle_with_csrf_passes(tmp_path):
    app = _make_app(tmp_path)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "admin"
        sess["tenant_id"] = "1"
        sess["CSRF_TOKEN"] = "tok123"
    r = client.post(
        "/api/kitchen/planering/normal_exclusions/toggle",
        json=_payload(),
        headers={"X-CSRF-Token": "tok123"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)