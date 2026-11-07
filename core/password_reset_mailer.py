"""Provider-independent SMTP delivery for password reset messages."""

from __future__ import annotations

import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Mapping
from urllib.parse import urlsplit

from .password_reset import (
    PasswordResetDeliveryError,
    PasswordResetMailer,
    reset_url_allows_insecure,
)


_SECURITY_MODES = {"starttls", "implicit_tls"}
_MAX_TIMEOUT_SECONDS = 60.0


def _setting(config: Mapping[str, object], name: str) -> str:
    return str(config.get(name) or os.getenv(name) or "").strip()


def _validate_header_value(value: str, field: str) -> str:
    if not value or "\r" in value or "\n" in value:
        raise PasswordResetDeliveryError(f"invalid SMTP {field}")
    return value


def _validate_address(value: str, field: str, *, allow_display_name: bool = False) -> str:
    value = _validate_header_value(value.strip(), field)
    _, address = parseaddr(value)
    if not address or (not allow_display_name and address != value) or "@" not in address:
        raise PasswordResetDeliveryError(f"invalid SMTP {field}")
    return address


class SMTPPasswordResetMailer:
    """Send reset messages using authenticated SMTP with mandatory TLS."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        security: str,
        timeout: float,
        allow_insecure_public_url: bool = False,
    ) -> None:
        self._host = _validate_header_value(host.strip(), "host")
        self._port = port
        self._username = _validate_header_value(username.strip(), "username")
        self._password = password
        self._sender = _validate_address(sender, "sender", allow_display_name=True)
        self._security = security
        self._timeout = timeout
        self._allow_insecure_public_url = allow_insecure_public_url

    def __call__(self, recipient: str, reset_url: str) -> None:
        recipient = _validate_address(recipient, "recipient")
        reset_url = _validate_header_value(reset_url.strip(), "reset URL")
        parsed_url = urlsplit(reset_url)
        is_loopback = parsed_url.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed_url.scheme == "https":
            pass
        elif (
            parsed_url.scheme == "http"
            and self._allow_insecure_public_url
            and is_loopback
        ):
            pass
        else:
            raise PasswordResetDeliveryError("password reset URL must use HTTPS")

        message = EmailMessage()
        message["Subject"] = "Återställ ditt Yuplan-lösenord"
        message["From"] = self._sender
        message["To"] = recipient
        message.set_content(
            "Hej,\n\n"
            "Vi fick en begäran om att återställa lösenordet för ditt Yuplan-konto.\n"
            f"Öppna länken inom 30 minuter:\n{reset_url}\n\n"
            "Om du inte begärde detta kan du ignorera meddelandet.\n\n"
            "Vänliga hälsningar,\nYuplan"
        )
        escaped_url = html.escape(reset_url, quote=True)
        message.add_alternative(
            "<html><body>"
            "<p>Hej,</p>"
            "<p>Vi fick en begäran om att återställa lösenordet för ditt Yuplan-konto.</p>"
            "<p><a href=\""
            + escaped_url
            + "\">Återställ lösenordet</a></p>"
            "<p>Länken gäller i 30 minuter. Om du inte begärde detta kan du ignorera "
            "meddelandet.</p>"
            "<p>Vänliga hälsningar,<br>Yuplan</p>"
            "</body></html>",
            subtype="html",
        )

        try:
            if self._security == "implicit_tls":
                with smtplib.SMTP_SSL(
                    self._host,
                    self._port,
                    timeout=self._timeout,
                    context=ssl.create_default_context(),
                ) as client:
                    client.login(self._username, self._password)
                    client.send_message(message)
            else:
                with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
                    client.ehlo()
                    client.starttls(context=ssl.create_default_context())
                    client.ehlo()
                    client.login(self._username, self._password)
                    client.send_message(message)
        except PasswordResetDeliveryError:
            raise
        except (OSError, smtplib.SMTPException, TimeoutError) as exc:
            raise PasswordResetDeliveryError("SMTP password reset delivery failed") from exc


def smtp_mailer_from_config(config: Mapping[str, object]) -> PasswordResetMailer:
    host = _setting(config, "PASSWORD_RESET_SMTP_HOST")
    port_value = _setting(config, "PASSWORD_RESET_SMTP_PORT")
    username = _setting(config, "PASSWORD_RESET_SMTP_USERNAME")
    password = _setting(config, "PASSWORD_RESET_SMTP_PASSWORD")
    sender = _setting(config, "PASSWORD_RESET_SMTP_FROM")
    security = (_setting(config, "PASSWORD_RESET_SMTP_SECURITY") or "starttls").lower()
    timeout_value = _setting(config, "PASSWORD_RESET_SMTP_TIMEOUT") or "10"

    if not all((host, port_value, username, password, sender)):
        raise PasswordResetDeliveryError("SMTP password reset configuration is incomplete")
    if security not in _SECURITY_MODES:
        raise PasswordResetDeliveryError("SMTP password reset TLS mode is invalid")
    try:
        port = int(port_value)
        timeout = float(timeout_value)
    except ValueError as exc:
        raise PasswordResetDeliveryError("SMTP password reset port or timeout is invalid") from exc
    if not 1 <= port <= 65535 or not 0 < timeout <= _MAX_TIMEOUT_SECONDS:
        raise PasswordResetDeliveryError("SMTP password reset port or timeout is out of range")
    return SMTPPasswordResetMailer(
        host=host,
        port=port,
        username=username,
        password=password,
        sender=sender,
        security=security,
        timeout=timeout,
        allow_insecure_public_url=reset_url_allows_insecure(config),
    )
