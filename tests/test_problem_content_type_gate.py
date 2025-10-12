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
        # seed superuser auth in session
        with client.session_transaction() as sess:
            sess["user_id"] = 1
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
        assert data.get("type", "").startswith("https://example.com/errors/")
