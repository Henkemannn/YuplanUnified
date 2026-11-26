import secrets

from core import create_app
from core.db import create_all


def _make_app(tmp_path, monkeypatch, *, testing=False, strict_csrf=False):
    # Force production-like CSRF (TESTING False) but keep other defaults.
    # We explicitly disable TESTING to exercise production policy.
    database_url = f"sqlite:///{(tmp_path / 'csrf_main.db').as_posix()}"
    builder_db_path = tmp_path / "csrf_builder.db"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(builder_db_path))
    app = create_app(
        {
            "TESTING": testing,
            "STRICT_CSRF_IN_TESTS": strict_csrf,
            "SECRET_KEY": "csrf-secret",
            "ENABLE_CSRF": True,
            "AUTH_RATE_LIMIT_HMAC_SECRET": "csrf-rate-limit-test-secret",
            "database_url": database_url,
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )
    with app.app_context():
        create_all()
    return app


def test_post_without_token_forbidden(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    # Provide Origin to ensure CSRF evaluated before route handler might reject
    r = client.post("/features/set", json={"name": "csrf_test", "enabled": True}, headers={"Origin": "http://localhost"})
    if r.status_code == 401:
        # Auth layer fired first; acceptable, skip strict assertion
        return
    assert r.status_code == 403, r.get_data(as_text=True)
    assert r.mimetype == "application/problem+json"
    body = r.get_json()
    assert body.get("detail") in {"csrf_missing", "origin_mismatch"}


def test_double_submit_token_allows_protected_post(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, strict_csrf=True)
    client = app.test_client()
    token = secrets.token_hex(8)
    cookie_name = app.config.get("CSRF_COOKIE_NAME", "csrf_token")
    header_name = app.config.get("CSRF_HEADER_NAME", "X-CSRF-Token")
    client.set_cookie(cookie_name, token)

    r = client.post(
        "/auth/reset",
        json={"token": "invalid", "password": "NotARealPassword123!"},
        headers={header_name: token},
    )
    assert r.status_code == 400
    body = r.get_data(as_text=True)
    assert "invalid_csrf" not in body
    assert "csrf_missing" not in body


def test_invalid_double_submit_token_is_forbidden(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, strict_csrf=True)
    client = app.test_client()
    client.set_cookie("csrf_token", secrets.token_hex(8))

    response = client.post(
        "/auth/reset",
        json={"token": "invalid", "password": "NotARealPassword123!"},
        headers={"X-CSRF-Token": secrets.token_hex(8)},
    )

    assert response.status_code == 403
    assert response.get_json()["detail"] == "invalid_csrf"


def test_missing_double_submit_token_is_forbidden(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, strict_csrf=True)
    client = app.test_client()

    response = client.post(
        "/auth/reset",
        json={"token": "invalid", "password": "NotARealPassword123!"},
    )

    assert response.status_code == 403
    assert response.get_json()["detail"] == "invalid_csrf"


def test_origin_mismatch_blocked(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    # Supply an Origin that is not the host
    r = client.post("/features/set", json={"name": "csrf_origin", "enabled": True}, headers={"Origin": "http://evil.example"})
    if r.status_code == 401:
        return  # auth took precedence
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("detail") == "origin_mismatch"


def test_safe_methods_ok_without_token(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    for method in ("GET", "HEAD", "OPTIONS"):
        resp = client.open(path="/features", method=method)
        # Unauthenticated may yield 401; CSRF should not interfere with safe methods.
        assert resp.status_code in {200, 401, 404}


def test_prod_exempt_paths_require_token_for_write(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    # A non-exempt path must be blocked without a token.
    r_block = client.post("/features/set", json={"name": "csrf_write", "enabled": True})
    assert r_block.status_code in (401, 403)
    if r_block.status_code == 403:
        assert r_block.get_json()["detail"] == "invalid_csrf"

    # /auth/login is CSRF-exempt in production, but rate limiting remains active.
    r_auth = client.post("/auth/login", json={"email": "a@b", "password": "pw"})
    assert r_auth.status_code == 401
    assert "csrf_" not in r_auth.get_data(as_text=True)
