import pytest

from core.app_factory import create_app


STRONG_SECRET = "production-session-key-" + "a" * 48
STRONG_JWT_SECRET = "production-jwt-key-" + "b" * 48


def _production_env(monkeypatch):
    monkeypatch.setenv("DEPLOY_ENV", "production")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", STRONG_JWT_SECRET)
    monkeypatch.setenv("SECRET_KEY", "")


def test_production_start_rejects_missing_secret_key(monkeypatch):
    _production_env(monkeypatch)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"TESTING": False, "SECRET_KEY": ""})


@pytest.mark.parametrize("secret_key", ("change-me", "test", "dev-static-secret-key-0123456789abcdef0123456789abcdef"))
def test_production_start_rejects_known_weak_secret_keys(monkeypatch, secret_key):
    _production_env(monkeypatch)

    with pytest.raises(RuntimeError, match="SECRET_KEY") as exc_info:
        create_app({"TESTING": False, "SECRET_KEY": secret_key})

    assert secret_key not in str(exc_info.value)


def test_production_start_accepts_strong_secret_and_preserves_it(monkeypatch):
    _production_env(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", STRONG_SECRET)

    first = create_app({"TESTING": False})
    second = create_app({"TESTING": False})

    assert first.config["SECRET_KEY"] == STRONG_SECRET
    assert second.config["SECRET_KEY"] == STRONG_SECRET


def test_session_cookie_round_trips_between_instances_with_stable_secret(monkeypatch):
    _production_env(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", STRONG_SECRET)

    first = create_app({"TESTING": True})
    second = create_app({"TESTING": True})

    @first.get("/test-session")
    def first_session():
        from flask import jsonify, session

        return jsonify(marker=session.get("marker"))

    @second.get("/test-session")
    def second_session():
        from flask import jsonify, session

        return jsonify(marker=session.get("marker"))

    first_client = first.test_client()
    with first_client.session_transaction() as sess:
        sess["marker"] = "stable"
    cookie = first_client.get_cookie("session")
    assert cookie is not None

    second_client = second.test_client()
    second_client.set_cookie("session", cookie.value)
    assert second_client.get("/test-session").get_json() == {"marker": "stable"}


def test_explicit_test_mode_keeps_deterministic_test_secret(monkeypatch):
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FLASK_ENV", "test")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SECRET_KEY", "")

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": "sqlite:///:memory:",
        }
    )

    assert app.config["SECRET_KEY"] == "test"
