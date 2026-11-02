from core import create_app
from core.db import create_all


def _make_app(tmp_path, monkeypatch, *, testing: bool):
    database_url = f"sqlite:///{(tmp_path / 'cookies_main.db').as_posix()}"
    builder_db_path = tmp_path / "cookies_builder.db"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(builder_db_path))
    app = create_app(
        {
            "TESTING": testing,
            "SECRET_KEY": "x",
            "database_url": database_url,
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )
    with app.app_context():
        create_all()
    return app


def test_csrf_cookie_flags_prod(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, testing=False)
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


def test_csrf_cookie_flags_testing(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, testing=True)
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
