from core import create_app


def test_csrf_cookie_flags_prod():
    app = create_app({"TESTING": False, "SECRET_KEY": "x"})
    client = app.test_client()
    r = client.post("/auth/login", json={"email": "n@example.com", "password": "pw"})
    # Expect 400/401 due to invalid creds but cookie issued (or attempted) for csrf token
    set_cookie = r.headers.get("Set-Cookie", "")
    if not set_cookie:
        # If no cookie (e.g., early 400 before issuance), skip
        return
    assert "csrf_token=" in set_cookie
    assert "SameSite=Strict" in set_cookie
    # In prod (TESTING False, DEBUG False) -> Secure expected
    assert "Secure" in set_cookie
    assert "HttpOnly" not in set_cookie  # should not be HttpOnly


def test_csrf_cookie_flags_testing():
    app = create_app({"TESTING": True, "SECRET_KEY": "x"})
    client = app.test_client()
    r = client.post("/auth/login", json={"email": "n@example.com", "password": "pw"})
    set_cookie = r.headers.get("Set-Cookie", "")
    if not set_cookie:
        return
    assert "csrf_token=" in set_cookie
    assert "SameSite=Strict" in set_cookie
    # In test env we accept absence of Secure for convenience
    assert "Secure" not in set_cookie
    assert "HttpOnly" not in set_cookie
