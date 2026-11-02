import os

import pytest

from core.app_factory import create_app

PILOT_PATHS = [
    "/superuser/impersonate/start",
]


@pytest.fixture(scope="module")
def app():
    os.environ["YUPLAN_PROBLEM_ONLY"] = "1"
    return create_app({"TESTING": True})


@pytest.fixture()
def client(app):
    return app.test_client()


def test_pilot_endpoints_return_problem_json(client):
    for path in PILOT_PATHS:
        from core.db import get_session
        from core.models import User

        db = get_session()
        try:
            user = db.query(User).filter(User.id == 1).first()
            if user is None:
                db.add(User(id=1, tenant_id=1, username="problem-superuser", email="problem-superuser@example.test", password_hash="!", role="superuser", is_active=True, auth_version=1))
            else:
                user.tenant_id = 1
                user.role = "superuser"
                user.is_active = True
                user.auth_version = 1
            db.commit()
        finally:
            db.close()
        # seed superuser auth in session
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["auth_version"] = 1
            sess["role"] = "superuser"
            sess["roles"] = ["superuser"]
            sess["tenant_id"] = 1
        resp = client.post(path, json={})  # trigger validation/forbidden (tenant_id missing)
        assert resp.mimetype == "application/problem+json", (
            f"{path} did not return problem+json (got {resp.mimetype})"
        )
        data = resp.get_json()
        assert data.get("status") in (400, 403, 422)
        assert data.get("request_id")
        assert data.get("type", "").startswith(
            ("https://example.com/problems/", "https://example.com/errors/")
        )
