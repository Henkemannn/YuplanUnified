"""Password reset workflow and its persistent abuse controls."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from time import sleep
from typing import Callable, Protocol
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from .models import PasswordResetThrottle, PasswordResetToken, User


class PasswordResetStoreError(RuntimeError):
    """Raised when reset state cannot be safely read or written."""


class PasswordResetDeliveryError(RuntimeError):
    """Raised when the configured reset mail adapter cannot deliver a message."""


class PasswordResetMailer(Protocol):
    def __call__(self, recipient: str, reset_url: str) -> None: ...


@dataclass(frozen=True)
class PasswordResetResult:
    sent: bool
    throttled: bool = False


def _now_epoch() -> int:
    return int(time.time())


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PasswordResetService:
    TOKEN_TTL_SECONDS = 30 * 60
    ACCOUNT_WINDOW_SECONDS = 15 * 60
    ACCOUNT_MAX_REQUESTS = 3
    ACCOUNT_LOCK_SECONDS = 15 * 60
    IP_WINDOW_SECONDS = 15 * 60
    IP_MAX_REQUESTS = 10
    IP_LOCK_SECONDS = 5 * 60

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        hmac_secret: str,
        clock: Callable[[], int] = _now_epoch,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.02,
    ) -> None:
        if not hmac_secret.strip():
            raise PasswordResetStoreError("PASSWORD_RESET_HMAC_SECRET is required")
        self._session_factory = session_factory
        self._hmac_secret = hmac_secret.encode("utf-8")
        self._clock = clock
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds

    @classmethod
    def from_config(
        cls,
        session_factory: Callable[[], Session],
        config: dict[str, object],
        *,
        clock: Callable[[], int] = _now_epoch,
    ) -> PasswordResetService:
        secret = str(
            config.get("PASSWORD_RESET_HMAC_SECRET")
            or os.getenv("PASSWORD_RESET_HMAC_SECRET")
            or ""
        ).strip()
        return cls(
            session_factory,
            hmac_secret=secret,
            clock=clock,
        )

    def request_reset(
        self,
        email: str,
        ip_address: str,
        *,
        mailer: PasswordResetMailer,
        public_base_url: str,
    ) -> PasswordResetResult:
        normalized_email = self._normalize_email(email)
        normalized_ip = ip_address.strip() or "na"
        account_hash = self._key_hash("account", normalized_email or "<empty>")
        ip_hash = self._key_hash("ip", normalized_ip)
        now = self._clock()
        token: str | None = None
        token_hash: str | None = None

        def operation(session: Session) -> PasswordResetResult:
            nonlocal token, token_hash
            with session.begin():
                rows = self._lock_throttle_rows(session, account_hash, ip_hash, now)
                decision = self._record_request(rows, now)
                if not decision:
                    return PasswordResetResult(sent=False, throttled=True)
                user = session.execute(
                    select(User).where(
                        User.email.is_not(None),
                        text("lower(users.email) = :email"),
                        User.is_active.is_(True),
                        User.deleted_at.is_(None),
                    ).params(email=normalized_email)
                ).scalar_one_or_none()
                if user is None:
                    return PasswordResetResult(sent=False)
                token = secrets.token_urlsafe(32)
                token_hash = self._token_hash(token)
                session.execute(
                    text(
                        """
                        UPDATE password_reset_tokens
                        SET revoked_at=:now
                        WHERE user_id=:user_id
                          AND used_at IS NULL
                          AND revoked_at IS NULL
                        """
                    ),
                    {"now": now, "user_id": int(user.id)},
                )
                session.add(
                    PasswordResetToken(
                        user_id=int(user.id),
                        token_hash=token_hash,
                        created_at=now,
                        expires_at=now + self.TOKEN_TTL_SECONDS,
                    )
                )
                return PasswordResetResult(sent=True)

        result = self._run(operation)
        if not result.sent or token is None or token_hash is None:
            return result
        try:
            mailer(str(normalized_email), self.build_reset_url(public_base_url, token))
        except Exception as exc:
            self._revoke_token(token_hash, self._clock())
            raise PasswordResetDeliveryError("password reset delivery failed") from exc
        return result

    def consume_reset(self, token: str, new_password: str) -> None:
        if not token.strip():
            raise ValueError("reset token is required")
        if len(new_password) < 6:
            raise ValueError("password must be at least 6 characters")
        now = self._clock()
        token_hash = self._token_hash(token)

        def operation(session: Session) -> None:
            with session.begin():
                claimed = session.execute(
                    text(
                        """
                        UPDATE password_reset_tokens
                        SET used_at=:now
                        WHERE token_hash=:token_hash
                          AND used_at IS NULL
                          AND revoked_at IS NULL
                          AND expires_at > :now
                        """
                    ),
                    {"now": now, "token_hash": token_hash},
                )
                if claimed.rowcount != 1:
                    raise ValueError("invalid or expired reset token")
                reset = session.execute(
                    select(PasswordResetToken)
                    .where(PasswordResetToken.token_hash == token_hash)
                    .with_for_update()
                ).scalar_one_or_none()
                if (
                    reset is None
                    or reset.revoked_at is not None
                ):
                    raise ValueError("invalid or expired reset token")
                user = session.execute(
                    select(User)
                    .where(User.id == reset.user_id)
                    .with_for_update()
                ).scalar_one_or_none()
                if user is None or not user.is_active or user.deleted_at is not None:
                    raise ValueError("invalid or expired reset token")
                user.password_hash = _generate_password_hash(new_password)
                user.auth_version = (user.auth_version or 1) + 1
                user.refresh_token_jti = None
                user.must_change_password = False
                session.execute(
                    text(
                        """
                        UPDATE password_reset_tokens
                        SET revoked_at=:now
                        WHERE user_id=:user_id
                          AND id != :token_id
                          AND used_at IS NULL
                          AND revoked_at IS NULL
                        """
                    ),
                    {"now": now, "user_id": int(user.id), "token_id": int(reset.id)},
                )

        self._run(operation)

    @staticmethod
    def build_reset_url(public_base_url: str, token: str) -> str:
        parts = urlsplit(public_base_url.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise PasswordResetDeliveryError("PASSWORD_RESET_PUBLIC_BASE_URL is invalid")
        if parts.query or parts.fragment:
            raise PasswordResetDeliveryError("PASSWORD_RESET_PUBLIC_BASE_URL must not contain query or fragment")
        base = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
        return f"{base}/auth/reset?token={token}"

    def _lock_throttle_rows(
        self,
        session: Session,
        account_hash: str,
        ip_hash: str,
        now: int,
    ) -> dict[str, PasswordResetThrottle]:
        values = (("account", account_hash), ("ip", ip_hash))
        for scope, key_hash in values:
            session.execute(
                text(
                    """
                    INSERT INTO password_reset_throttles
                        (scope, key_hash, request_count, window_started_at, updated_at)
                    VALUES (:scope, :key_hash, 0, :now, :updated_at)
                    ON CONFLICT (scope, key_hash) DO NOTHING
                    """
                ),
                {"scope": scope, "key_hash": key_hash, "now": now, "updated_at": _utc_now()},
            )
        rows: dict[str, PasswordResetThrottle] = {}
        for scope, key_hash in values:
            session.execute(
                text(
                    """
                    UPDATE password_reset_throttles
                    SET updated_at=:updated_at
                    WHERE scope=:scope AND key_hash=:key_hash
                    """
                ),
                {"scope": scope, "key_hash": key_hash, "updated_at": _utc_now()},
            )
            rows[scope] = session.execute(
                select(PasswordResetThrottle)
                .where(
                    PasswordResetThrottle.scope == scope,
                    PasswordResetThrottle.key_hash == key_hash,
                )
                .with_for_update()
            ).scalar_one()
        return rows

    def _record_request(
        self,
        rows: dict[str, PasswordResetThrottle],
        now: int,
    ) -> bool:
        policies = {
            "account": (
                self.ACCOUNT_WINDOW_SECONDS,
                self.ACCOUNT_MAX_REQUESTS,
                self.ACCOUNT_LOCK_SECONDS,
            ),
            "ip": (self.IP_WINDOW_SECONDS, self.IP_MAX_REQUESTS, self.IP_LOCK_SECONDS),
        }
        for scope, row in rows.items():
            window, maximum, lock_seconds = policies[scope]
            if row.locked_until is not None and row.locked_until <= now:
                row.locked_until = None
                row.request_count = 0
            if row.window_started_at <= 0 or now - row.window_started_at >= window:
                row.window_started_at = now
                row.request_count = 0
                if row.locked_until is None or row.locked_until <= now:
                    row.locked_until = None
            if row.locked_until is not None and row.locked_until > now:
                return False
            if row.request_count >= maximum:
                row.locked_until = now + lock_seconds
                return False
        for row in rows.values():
            row.request_count += 1
            row.updated_at = _utc_now()
        return True

    def _revoke_token(self, token_hash: str, now: int) -> None:
        def operation(session: Session) -> None:
            with session.begin():
                session.execute(
                    text(
                        """
                        UPDATE password_reset_tokens
                        SET revoked_at=:now
                        WHERE token_hash=:token_hash
                          AND used_at IS NULL
                          AND revoked_at IS NULL
                        """
                    ),
                    {"now": now, "token_hash": token_hash},
                )

        self._run(operation)

    def _run(self, operation):
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            session: Session | None = None
            try:
                session = self._session_factory()
                return operation(session)
            except OperationalError as exc:
                last_error = exc
                if not self._is_sqlite_lock(exc) or attempt + 1 >= self._max_retries:
                    raise PasswordResetStoreError("password reset store unavailable") from exc
                sleep(self._retry_delay_seconds * (attempt + 1))
            except (DBAPIError, SQLAlchemyError) as exc:
                raise PasswordResetStoreError("password reset store unavailable") from exc
            except RuntimeError as exc:
                if isinstance(exc, PasswordResetStoreError):
                    raise
                raise PasswordResetStoreError("password reset store unavailable") from exc
            finally:
                if session is not None:
                    session.close()
        raise PasswordResetStoreError("password reset store unavailable") from last_error

    @staticmethod
    def _is_sqlite_lock(exc: OperationalError) -> bool:
        message = str(exc).lower()
        return "database is locked" in message or "database table is locked" in message

    def _key_hash(self, scope: str, value: str) -> str:
        return hmac.new(
            self._hmac_secret,
            f"reset-key:{scope}:{value}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _token_hash(self, token: str) -> str:
        return hmac.new(
            self._hmac_secret,
            f"reset-token:{token}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()


def _generate_password_hash(password: str) -> str:
    from werkzeug.security import generate_password_hash

    return generate_password_hash(password)
