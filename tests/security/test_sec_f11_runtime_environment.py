import pytest

from core.app_factory import create_app
from core.config import auth_bypass_allowed, configured_runtime_environment


STRONG_SECRET = "synthetic-sec-f11-secret-0123456789abcdef"
STRONG_JWT = "synthetic-sec-f11-jwt-0123456789abcdef"


def _isolated_app(tmp_path, monkeypatch, *, environment=None, testing=False, **overrides):
    for name in (
        "DEPLOY_ENV",
        "APP_ENV",
        "FLASK_ENV",
        "FLY_APP_NAME",
        "SECRET_KEY",
        "JWT_SECRET",
        "DATABASE_URL",
        "BUILDER_DB_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    if environment:
        for name, value in environment.items():
            monkeypatch.setenv(name, value)

    database_url = f"sqlite:///{(tmp_path / 'sec-f11-runtime.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(tmp_path / "builder.db"))
    config = {
        "TESTING": testing,
        "SECRET_KEY": STRONG_SECRET,
        "JWT_SECRET": STRONG_JWT,
        "database_url": database_url,
        "BUILDER_DB_PATH": str(tmp_path / "builder.db"),
    }
    config.update(overrides)
    return create_app(config)


@pytest.mark.parametrize(
    "environment",
    (
        {"DEPLOY_ENV": "dev", "APP_ENV": "production"},
        {"DEPLOY_ENV": "production", "APP_ENV": "dev"},
        {"DEPLOY_ENV": "dev", "FLASK_ENV": "pilot"},
        {"DEPLOY_ENV": "staging", "APP_ENV": "dev"},
    ),
)
def test_conflicting_environment_variables_fail_closed(
    tmp_path, monkeypatch, environment
):
    with pytest.raises(RuntimeError, match="Conflicting environment variables"):
        _isolated_app(tmp_path, monkeypatch, environment=environment)


@pytest.mark.parametrize("environment_name", ("dev", "development", "local", "test", "testing"))
def test_explicit_local_environment_remains_available(
    tmp_path, monkeypatch, environment_name
):
    app = _isolated_app(
        tmp_path,
        monkeypatch,
        environment={"APP_ENV": environment_name},
        testing=False,
        SECRET_KEY="",
        JWT_SECRET="",
    )

    assert configured_runtime_environment() == environment_name
    assert auth_bypass_allowed() is True
    assert app.config["SECRET_KEY"]


@pytest.mark.parametrize(
    "environment",
    (
        {"APP_ENV": "staging"},
        {"DEPLOY_ENV": "pilot"},
        {"FLASK_ENV": "production"},
    ),
)
@pytest.mark.parametrize("secret_name", ("SECRET_KEY", "JWT_SECRET"))
def test_deployed_environment_rejects_missing_or_weak_secret(
    tmp_path, monkeypatch, environment, secret_name
):
    weak_value = "synthetic-weak"
    overrides = {secret_name: "" if secret_name == "SECRET_KEY" else weak_value}
    if secret_name == "JWT_SECRET":
        overrides["SECRET_KEY"] = STRONG_SECRET
    else:
        overrides["JWT_SECRET"] = STRONG_JWT

    with pytest.raises(RuntimeError, match="strong|missing/weak"):
        _isolated_app(
            tmp_path,
            monkeypatch,
            environment=environment,
            testing=True,
            **overrides,
        )


def test_staging_accepts_only_strong_synthetic_secrets_and_blocks_bypass(
    tmp_path, monkeypatch
):
    app = _isolated_app(
        tmp_path,
        monkeypatch,
        environment={"DEPLOY_ENV": "staging"},
        testing=True,
    )

    assert app.config["SECRET_KEY"] == STRONG_SECRET
    assert app.config["JWT_SECRET"] == STRONG_JWT
    assert auth_bypass_allowed(testing=True) is False


def test_fly_with_local_environment_flags_rejects_local_fallback(
    tmp_path, monkeypatch
):
    with pytest.raises(RuntimeError, match="strong|missing/weak"):
        _isolated_app(
            tmp_path,
            monkeypatch,
            environment={"APP_ENV": "dev", "FLY_APP_NAME": "synthetic-f11-app"},
            testing=True,
            SECRET_KEY="",
            JWT_SECRET="",
        )


def test_fly_without_environment_rejects_test_jwt_fallback(
    tmp_path, monkeypatch
):
    with pytest.raises(RuntimeError, match="missing/weak"):
        _isolated_app(
            tmp_path,
            monkeypatch,
            environment={"FLY_APP_NAME": "synthetic-f11-app"},
            testing=True,
            SECRET_KEY=STRONG_SECRET,
            JWT_SECRET="",
        )


def test_unset_environment_does_not_enable_normal_dev_fallback(
    tmp_path, monkeypatch
):
    app = _isolated_app(
        tmp_path,
        monkeypatch,
        testing=False,
        SECRET_KEY="",
        JWT_SECRET="",
    )

    assert configured_runtime_environment() == ""
    assert app.config["SECRET_KEY"] == ""
    assert app.config["JWT_SECRET"] == ""
    assert auth_bypass_allowed() is False


def test_unknown_environment_does_not_enable_local_fallback(
    tmp_path, monkeypatch
):
    app = _isolated_app(
        tmp_path,
        monkeypatch,
        environment={"APP_ENV": "synthetic-unknown"},
        testing=False,
        SECRET_KEY="",
        JWT_SECRET="",
    )

    assert app.config["SECRET_KEY"] == ""
    assert app.config["JWT_SECRET"] == ""
    assert auth_bypass_allowed() is False


def test_fly_with_strong_secrets_still_blocks_bypass(tmp_path, monkeypatch):
    app = _isolated_app(
        tmp_path,
        monkeypatch,
        environment={"APP_ENV": "dev", "FLY_APP_NAME": "synthetic-f11-app"},
        testing=True,
    )

    assert app.config["SECRET_KEY"] == STRONG_SECRET
    assert app.config["JWT_SECRET"] == STRONG_JWT
    assert auth_bypass_allowed(testing=True) is False


def test_environment_conflict_error_does_not_echo_configuration_values(
    tmp_path, monkeypatch
):
    marker = "SYNTHETIC_SECRET_MUST_NOT_BE_ECHOED"
    with pytest.raises(RuntimeError) as error:
        _isolated_app(
            tmp_path,
            monkeypatch,
            environment={"DEPLOY_ENV": "dev", "APP_ENV": "production"},
            SECRET_KEY=marker,
            JWT_SECRET=marker,
        )

    assert marker not in str(error.value)
