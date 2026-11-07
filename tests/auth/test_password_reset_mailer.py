from __future__ import annotations

from email.message import EmailMessage

import pytest

from core.app_factory import create_app
from core.password_reset import (
    PasswordResetDeliveryError,
    PasswordResetService,
    reset_url_allows_insecure,
)
from core.password_reset_mailer import SMTPPasswordResetMailer, smtp_mailer_from_config


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, **kwargs):
        self.host = host
        self.port = port
        self.kwargs = kwargs
        self.started_tls = False
        self.logged_in = None
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def ehlo(self):
        return None

    def starttls(self, *, context):
        self.started_tls = context

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message: EmailMessage):
        self.message = message


def _config(**overrides):
    config = {
        "PASSWORD_RESET_SMTP_HOST": "smtp.example.test",
        "PASSWORD_RESET_SMTP_PORT": "587",
        "PASSWORD_RESET_SMTP_USERNAME": "mailer@example.test",
        "PASSWORD_RESET_SMTP_PASSWORD": "smtp-secret",
        "PASSWORD_RESET_SMTP_FROM": "Yuplan <noreply@example.test>",
        "PASSWORD_RESET_SMTP_SECURITY": "starttls",
        "PASSWORD_RESET_SMTP_TIMEOUT": "5",
    }
    config.update(overrides)
    return config


def test_smtp_mailer_sends_text_and_html_over_starttls(monkeypatch):
    _FakeSMTP.instances.clear()
    monkeypatch.setattr("core.password_reset_mailer.smtplib.SMTP", _FakeSMTP)
    mailer = smtp_mailer_from_config(_config())

    mailer("user@example.test", "https://pilot.example.test/auth/reset?token=abc")

    client = _FakeSMTP.instances[0]
    assert client.host == "smtp.example.test"
    assert client.port == 587
    assert client.kwargs["timeout"] == 5.0
    assert client.started_tls
    assert client.logged_in == ("mailer@example.test", "smtp-secret")
    assert client.message is not None
    assert client.message["To"] == "user@example.test"
    assert len(client.message.get_payload()) == 2
    assert "30 minuter" in client.message.get_body(("plain",)).get_content()
    assert "https://pilot.example.test/auth/reset?token=abc" in client.message.get_body(("html",)).get_content()


def test_smtp_mailer_uses_implicit_tls_when_configured(monkeypatch):
    _FakeSMTP.instances.clear()
    monkeypatch.setattr("core.password_reset_mailer.smtplib.SMTP_SSL", _FakeSMTP)
    mailer = smtp_mailer_from_config(_config(
        PASSWORD_RESET_SMTP_PORT="465",
        PASSWORD_RESET_SMTP_SECURITY="implicit_tls",
    ))

    mailer("user@example.test", "https://pilot.example.test/auth/reset?token=abc")

    client = _FakeSMTP.instances[0]
    assert client.port == 465
    assert client.started_tls is False
    assert client.logged_in == ("mailer@example.test", "smtp-secret")


@pytest.mark.parametrize(
    "overrides",
    [
        {"PASSWORD_RESET_SMTP_HOST": ""},
        {"PASSWORD_RESET_SMTP_PASSWORD": ""},
        {"PASSWORD_RESET_SMTP_SECURITY": "plain"},
        {"PASSWORD_RESET_SMTP_PORT": "not-a-port"},
        {"PASSWORD_RESET_SMTP_TIMEOUT": "61"},
    ],
)
def test_smtp_mailer_rejects_unsafe_or_invalid_configuration(overrides):
    with pytest.raises(PasswordResetDeliveryError):
        smtp_mailer_from_config(_config(**overrides))


def test_smtp_mailer_rejects_header_injection_and_insecure_url(monkeypatch):
    monkeypatch.setattr("core.password_reset_mailer.smtplib.SMTP", _FakeSMTP)
    mailer = smtp_mailer_from_config(_config())

    with pytest.raises(PasswordResetDeliveryError):
        mailer("attacker@example.test\r\nBcc: victim@example.test", "https://pilot.example.test/auth/reset?token=abc")
    with pytest.raises(PasswordResetDeliveryError):
        mailer("user@example.test", "http://pilot.example.test/auth/reset?token=abc")


def test_smtp_mailer_allows_http_loopback_only_in_local_environment(monkeypatch):
    _FakeSMTP.instances.clear()
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setattr("core.password_reset_mailer.smtplib.SMTP", _FakeSMTP)
    mailer = smtp_mailer_from_config(_config())

    mailer("user@example.test", "http://127.0.0.1:5000/auth/reset?token=abc")

    assert _FakeSMTP.instances[0].message is not None
    with pytest.raises(PasswordResetDeliveryError):
        mailer("user@example.test", "http://example.test/auth/reset?token=abc")


@pytest.mark.parametrize("deploy_env", ["staging", "pilot", "production"])
def test_smtp_mailer_rejects_http_loopback_in_deployed_environment(
    monkeypatch,
    deploy_env,
):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DEPLOY_ENV", deploy_env)
    mailer = smtp_mailer_from_config(_config())

    with pytest.raises(PasswordResetDeliveryError):
        mailer("user@example.test", "http://localhost:5000/auth/reset?token=abc")


def test_smtp_mailer_rejects_http_loopback_in_fly_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.setenv("FLY_APP_NAME", "yuplan-local-test")
    mailer = smtp_mailer_from_config(_config())

    with pytest.raises(PasswordResetDeliveryError):
        mailer("user@example.test", "http://[::1]:5000/auth/reset?token=abc")


def test_smtp_mailer_converts_timeout_and_delivery_errors(monkeypatch):
    class _TimeoutSMTP(_FakeSMTP):
        def send_message(self, message):
            raise TimeoutError("timed out")

    monkeypatch.setattr("core.password_reset_mailer.smtplib.SMTP", _TimeoutSMTP)
    mailer = smtp_mailer_from_config(_config())

    with pytest.raises(PasswordResetDeliveryError):
        mailer("user@example.test", "https://pilot.example.test/auth/reset?token=abc")


def test_reset_base_url_requires_https_outside_local_development():
    with pytest.raises(PasswordResetDeliveryError):
        PasswordResetService.build_reset_url("http://pilot.example.test", "abc")
    assert (
        PasswordResetService.build_reset_url(
            "http://localhost:5000",
            "abc",
            allow_insecure=True,
        )
        == "http://localhost:5000/auth/reset?token=abc"
    )


def test_explicit_local_environment_allows_insecure_reset_url(monkeypatch):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    assert reset_url_allows_insecure({"APP_ENV": "dev", "TESTING": True})


@pytest.mark.parametrize("deploy_env", ["staging", "pilot", "production"])
def test_deployed_environments_never_allow_insecure_reset_urls(deploy_env, monkeypatch):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    assert not reset_url_allows_insecure(
        {"APP_ENV": "dev", "DEPLOY_ENV": deploy_env, "TESTING": True}
    )


def test_fly_never_allows_insecure_reset_urls_even_with_dev_testing(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "yuplan-pilot")
    assert not reset_url_allows_insecure(
        {"APP_ENV": "dev", "TESTING": True}
    )


def test_public_reset_base_url_reads_environment_and_preserves_explicit_override(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "PASSWORD_RESET_PUBLIC_BASE_URL",
        "https://yuplan-unified-staging.fly.dev",
    )
    env_app = create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{(tmp_path / 'env-config.db').as_posix()}",
        }
    )
    assert env_app.config["PASSWORD_RESET_PUBLIC_BASE_URL"] == (
        "https://yuplan-unified-staging.fly.dev"
    )

    override_app = create_app(
        {
            "TESTING": True,
            "database_url": f"sqlite:///{(tmp_path / 'override-config.db').as_posix()}",
            "PASSWORD_RESET_PUBLIC_BASE_URL": "https://test.example.test",
        }
    )
    assert override_app.config["PASSWORD_RESET_PUBLIC_BASE_URL"] == (
        "https://test.example.test"
    )
