from core import create_app
from flask import session


def test_step1_get_and_post_redirect_step2():
    app = create_app({"TESTING": True, "SECRET_KEY": "x"})
    client = app.test_client()
    # Establish superuser session
    with client.session_transaction() as s:
        s["user_id"] = 1
        s["role"] = "superuser"
        s["tenant_id"] = 1
    r = client.get("/ui/systemadmin/customers/new")
    assert r.status_code == 200
    assert b"Kundnamn" in r.data
    # Post minimal valid data; include csrf_token from session for tests
    with client.session_transaction() as s:
        tok = s.get("CSRF_TOKEN") or "dummy"
    resp = client.post(
        "/ui/systemadmin/customers/new/step1",
        data={
            "csrf_token": tok,
            "tenant_name": "Acme",
            "site_name": "Acme HQ",
            "customer_type": "Kommun",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "/ui/systemadmin/customers/new/contract" in resp.headers.get("Location", "")
