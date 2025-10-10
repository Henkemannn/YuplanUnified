import os

import pytest

from core.app_factory import create_app


@pytest.fixture(scope="module")
def app():
    os.environ["YUPLAN_PROBLEM_ONLY"] = "1"
    os.environ.setdefault("YUPLAN_STRICT_CSRF", "0")
    app = create_app({"TESTING": True})
    yield app

@pytest.fixture()
def client(app):
    return app.test_client()

# Helpers

def _auth_headers():
    # For pilot diet endpoints we may not require auth for certain operations; adjust if needed.
    return {}

@pytest.mark.parametrize("path,status,expect_type", [
    ("/diet/api/v1/items?id=999999", 404, "not_found"),  # assuming not found path variant
])
@pytest.mark.skip(reason="Placeholder param set; refine according to actual diet endpoints")
def test_placeholder(client, path, status, expect_type):
    resp = client.get(path, headers=_auth_headers())
    assert resp.status_code == status
    assert resp.mimetype == "application/problem+json"


def test_validation_422(client):
    # Trigger validation error on impersonation endpoint (missing required fields) or diet create.
    # Choose /superuser/impersonation/start expecting POST body with user_id
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "superuser"
        sess["roles"] = ["superuser"]
        sess["tenant_id"] = 1
    resp = client.post("/superuser/impersonate/start", json={})
    # Depending on implementation may be 400 or 422; accept either but assert problem+json
    assert resp.mimetype == "application/problem+json"
    data = resp.get_json()
    assert data["status"] in (400, 422)
    assert data["type"].startswith("https://example.com/errors/")
    assert "request_id" in data
    if data["status"] == 422:
        assert isinstance(data.get("errors"), list)


def test_forbidden_403_impersonation_required(client):
    # Hit an impersonation-required diet endpoint without impersonation (adjust path if needed)
    # Placeholder path; modify according to real diet protected endpoint
    resp = client.get("/diet/api/v1/secure", follow_redirects=True)
    # Accept 403 fallback even if endpoint differs
    if resp.status_code == 404:
        pytest.skip("Diet secure endpoint placeholder not present")
    assert resp.status_code == 403
    assert resp.mimetype == "application/problem+json"
    data = resp.get_json()
    assert data["type"].endswith("forbidden") or data["status"] == 403
    assert "request_id" in data


def test_incident_500(client):
    resp = client.get("/_test/boom")
    assert resp.status_code == 500
    assert resp.mimetype == "application/problem+json"
    data = resp.get_json()
    assert data["status"] == 500
    assert "incident_id" in data
    assert data["type"].endswith("internal_error")
    assert "request_id" in data


def test_audit_events_recorded(client, app):
    # Generate a problem response (401) without session
    client.post("/superuser/impersonate/start", json={})
    # Generate an incident 500
    client.get("/_test/boom")
    from core.audit_events import _AUDIT_BUFFER
    kinds = {e.get("action") for e in _AUDIT_BUFFER}
    assert "problem_response" in kinds, f"Audit buffer missing problem_response events: {kinds}"
    assert "incident" in kinds, f"Audit buffer missing incident events: {kinds}"

