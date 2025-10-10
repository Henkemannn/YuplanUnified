import os

import pytest

from core.app_factory import create_app


@pytest.fixture(scope="module")
def app():
    # ProblemDetails is canonical now; flag is ignored but kept for backward compat
    os.environ["YUPLAN_PROBLEM_ONLY"] = "0"
    app = create_app({"TESTING": True})
    yield app

@pytest.fixture()
def client(app):
    return app.test_client()

def test_problem_error_shape(client):
    # Trigger an error and expect RFC7807 problem+json
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "superuser"
        sess["roles"] = ["superuser"]
    resp = client.post("/superuser/impersonate/start", json={})
    assert resp.status_code in (400, 401, 403, 422)
    assert resp.mimetype == "application/problem+json"
    data = resp.get_json()
    assert data.get("status") in (400,401,403,422)
    assert data.get("type", "").startswith("https://example.com/errors/")
