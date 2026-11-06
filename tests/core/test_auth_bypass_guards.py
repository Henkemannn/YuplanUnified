import pytest
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.config import auth_bypass_allowed
from core.db import create_all, get_session
from core.models import Tenant, User


_BYPASS_ENV_VARS = (
    "DEPLOY_ENV",
    "APP_ENV",
    "FLASK_ENV",
    "STAGING_SIMPLE_AUTH",
    "DEMO_UI",
    "YUPLAN_DEV_HELPERS",
)


def _isolated_app(tmp_path, monkeypatch, *, testing: bool, **overrides):
    database_url = f"sqlite:///{(tmp_path / 'auth_bypass.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(tmp_path / "builder.db"))
    app_config = {
        "TESTING": testing,
        "SECRET_KEY": "test-auth-bypass-secret",
        "JWT_SECRET": "test-jwt-secret-0123456789abcdef0123456789abcdef",
        "database_url": database_url,
        "BUILDER_DB_PATH": str(tmp_path / "builder.db"),
    }
    app_config.update(overrides)
    app = create_app(app_config)
    with app.app_context():
        create_all()
    return app


@pytest.mark.parametrize("env_name", ("", "staging", "pilot", "production"))
def test_auth_bypass_policy_is_fail_closed_outside_local_or_test(monkeypatch, env_name):
    for name in _BYPASS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    if env_name:
        monkeypatch.setenv("DEPLOY_ENV", env_name)

    assert auth_bypass_allowed() is False


@pytest.mark.parametrize("env_name", ("dev", "development", "local", "test", "testing"))
def test_auth_bypass_policy_allows_explicit_local_environments(monkeypatch, env_name):
    for name in _BYPASS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", env_name)

    assert auth_bypass_allowed() is True
    assert auth_bypass_allowed(testing=True) is True


def test_auth_bypass_policy_stays_closed_on_fly(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("FLY_APP_NAME", "yuplan-unified-staging")

    assert auth_bypass_allowed() is False


@pytest.mark.parametrize(
    "environment",
    (
        {"FLY_APP_NAME": "yuplan-unified-staging", "APP_ENV": "dev"},
        {"DEPLOY_ENV": "pilot", "APP_ENV": "dev"},
        {"DEPLOY_ENV": "production", "APP_ENV": "dev"},
    ),
)
def test_deployed_environment_overrides_testing_and_blocks_bypass(
    tmp_path, monkeypatch, environment
):
    for name in _BYPASS_ENV_VARS + ("FLY_APP_NAME",):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DEMO_UI", "1")
    monkeypatch.setenv("STAGING_SIMPLE_AUTH", "1")
    monkeypatch.setenv("YUPLAN_DEV_HELPERS", "1")

    assert auth_bypass_allowed(testing=True) is False
    app = _isolated_app(tmp_path, monkeypatch, testing=True, DEMO_AUTH_ENABLED=True)
    assert app.config["SESSION_COOKIE_SECURE"] is True

    client = app.test_client()
    assert client.post("/auth/login", json={"role": "admin"}).status_code != 200
    assert client.get("/ui/dev-login", follow_redirects=False).status_code in (301, 302)
    assert client.get("/test-login").status_code == 404
    assert client.get("/ui/demo").status_code == 404
    assert client.get("/demo").status_code == 404
    assert client.get("/_routes").status_code == 404


def test_staging_simple_auth_cannot_bypass_normal_login(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPLOY_ENV", "staging")
    monkeypatch.setenv("STAGING_SIMPLE_AUTH", "1")
    app = _isolated_app(
        tmp_path,
        monkeypatch,
        testing=False,
        DEMO_AUTH_ENABLED=True,
    )

    response = app.test_client().post("/auth/login", json={"role": "admin"})

    assert response.status_code in (400, 401)
    assert response.get_json().get("demo") is None


def test_demo_ui_and_routes_are_not_registered_in_unknown_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPLOY_ENV", "")
    monkeypatch.setenv("APP_ENV", "")
    monkeypatch.setenv("FLASK_ENV", "")
    monkeypatch.setenv("DEMO_UI", "1")
    app = _isolated_app(tmp_path, monkeypatch, testing=False)

    client = app.test_client()

    assert client.get("/demo").status_code == 404
    assert client.get("/_routes").status_code == 404


def test_dev_login_is_not_available_in_staging(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPLOY_ENV", "staging")
    monkeypatch.setenv("YUPLAN_DEV_HELPERS", "1")
    app = _isolated_app(tmp_path, monkeypatch, testing=False)

    response = app.test_client().get("/ui/dev-login", follow_redirects=False)

    assert response.status_code in (301, 302)
    assert "/ui/login" in (response.headers.get("Location") or "")


def test_normal_login_sets_secure_session_cookie_in_deployed_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPLOY_ENV", "pilot")
    app = _isolated_app(tmp_path, monkeypatch, testing=False)
    with app.app_context():
        db = get_session()
        tenant = Tenant(name="Cookie Test Tenant")
        db.add(tenant)
        db.flush()
        db.add(
            User(
                tenant_id=tenant.id,
                email="cookie-test@example.test",
                username="cookie-test@example.test",
                password_hash=generate_password_hash("Passw0rd!"),
                role="superuser",
            )
        )
        db.commit()
        db.close()

    response = app.test_client().post(
        "/auth/login",
        json={"email": "cookie-test@example.test", "password": "Passw0rd!"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    cookies = response.headers.getlist("Set-Cookie")
    session_cookie = next(cookie for cookie in cookies if cookie.startswith("session="))
    assert "Secure" in session_cookie
    assert "HttpOnly" in session_cookie
    assert "SameSite=Lax" in session_cookie


def test_local_testing_login_keeps_http_session_cookie_usable(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    app = _isolated_app(tmp_path, monkeypatch, testing=True)

    assert app.config["SESSION_COOKIE_SECURE"] is False
