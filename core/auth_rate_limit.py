"""Persistent, atomic login-attempt throttling.

This module is intentionally not wired into the login endpoint yet. Callers
reserve an attempt before password verification and complete that reservation
after verification, so concurrent password checks cannot lose counter updates.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from time import sleep
from typing import Callable

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from .models import AuthLoginThrottle, AuthLoginThrottleReservation


class AuthRateLimitStoreError(RuntimeError):
    """Raised when the persistent throttle store cannot complete an operation."""


class AuthRateLimitConfigurationError(AuthRateLimitStoreError):
    """Raised when the required deployment-only HMAC secret is missing."""


class AuthRateLimitReservationError(AuthRateLimitStoreError):
    """Raised when a reservation is unknown, duplicated, or expired."""


@dataclass(frozen=True)
class AuthRateLimitPolicy:
    window_seconds: int
    max_failures: int
    lock_seconds: int

    def __post_init__(self) -> None:
        if self.window_seconds <= 0 or self.max_failures <= 0 or self.lock_seconds <= 0:
            raise ValueError("rate-limit policy values must be positive")


DEFAULT_ACCOUNT_POLICY = AuthRateLimitPolicy(
    window_seconds=300,
    max_failures=5,
    lock_seconds=600,
)
DEFAULT_IP_POLICY = AuthRateLimitPolicy(
    window_seconds=300,
    max_failures=50,
    lock_seconds=60,
)


@dataclass(frozen=True)
class AuthRateLimitDecision:
    allowed: bool
    retry_after: int = 0
    scope: str | None = None


@dataclass(frozen=True)
class AuthRateLimitLease:
    account_hash: str
    ip_hash: str
    allowed: bool
    reservation_token: str | None = None


@dataclass(frozen=True)
class _LockedThrottleRows:
    current: dict[str, AuthLoginThrottle]
    all_rows: dict[tuple[str, str], AuthLoginThrottle]
    expired_reservations: tuple[AuthLoginThrottleReservation, ...]


def configured_hmac_secret(config: dict[str, object] | None = None) -> str:
    """Return the dedicated deployment secret without falling back to another secret."""
    configured = (config or {}).get("AUTH_RATE_LIMIT_HMAC_SECRET")
    secret = str(configured or os.getenv("AUTH_RATE_LIMIT_HMAC_SECRET") or "").strip()
    if not secret:
        raise AuthRateLimitConfigurationError("AUTH_RATE_LIMIT_HMAC_SECRET is required")
    return secret


def _now_epoch() -> int:
    return int(time.time())


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuthLoginRateLimitStore:
    """Database-backed account and IP throttling with short atomic transactions."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        hmac_secret: str,
        account_policy: AuthRateLimitPolicy = DEFAULT_ACCOUNT_POLICY,
        ip_policy: AuthRateLimitPolicy = DEFAULT_IP_POLICY,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.02,
        reservation_ttl_seconds: int = 30,
        clock: Callable[[], int] = _now_epoch,
    ) -> None:
        if not hmac_secret.strip():
            raise AuthRateLimitConfigurationError("hmac_secret is required")
        if max_retries < 1:
            raise ValueError("max_retries must be positive")
        if reservation_ttl_seconds <= 0:
            raise ValueError("reservation_ttl_seconds must be positive")
        if reservation_ttl_seconds >= min(
            account_policy.window_seconds,
            ip_policy.window_seconds,
        ):
            raise ValueError("reservation TTL must be shorter than both rate-limit windows")
        self._session_factory = session_factory
        self._hmac_secret = hmac_secret.encode("utf-8")
        self._policies = {
            "account": account_policy,
            "ip": ip_policy,
        }
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._reservation_ttl_seconds = reservation_ttl_seconds
        self._clock = clock

    def key_hash(self, scope: str, value: str) -> str:
        """Return a stable HMAC digest without retaining the raw identifier."""
        if scope not in self._policies:
            raise ValueError("scope must be account or ip")
        normalized = value.strip().lower() if scope == "account" else value.strip()
        if not normalized:
            raise ValueError("throttle key value must not be empty")
        payload = f"{scope}:{normalized}".encode("utf-8")
        return hmac.new(self._hmac_secret, payload, hashlib.sha256).hexdigest()

    def begin_attempt(self, email: str, ip_address: str) -> tuple[AuthRateLimitDecision, AuthRateLimitLease]:
        account_hash = self.key_hash("account", email)
        ip_hash = self.key_hash("ip", ip_address)
        now = self._clock()

        def operation(session: Session) -> tuple[AuthRateLimitDecision, AuthRateLimitLease]:
            with session.begin():
                locked = self._lock_rows(session, account_hash, ip_hash, now)
                self._reclaim_expired_reservations(session, locked)
                decision = self._reserve(locked.current, now)
                if not decision.allowed:
                    return decision, AuthRateLimitLease(account_hash, ip_hash, False)
                token = secrets.token_urlsafe(32)
                session.add(
                    AuthLoginThrottleReservation(
                        reservation_hash=self._reservation_hash(token),
                        account_hash=account_hash,
                        ip_hash=ip_hash,
                        created_at=now,
                        expires_at=now + self._reservation_ttl_seconds,
                    )
                )
                return decision, AuthRateLimitLease(account_hash, ip_hash, True, token)

        return self._run(operation)

    def complete_attempt(
        self,
        lease: AuthRateLimitLease,
        *,
        success: bool,
    ) -> AuthRateLimitDecision:
        if not lease.allowed:
            raise ValueError("cannot complete a denied rate-limit lease")
        if not lease.reservation_token:
            raise AuthRateLimitReservationError("rate-limit lease has no reservation token")
        now = self._clock()

        def operation(session: Session) -> AuthRateLimitDecision | None:
            with session.begin():
                locked = self._lock_rows(session, lease.account_hash, lease.ip_hash, now)
                self._reclaim_expired_reservations(session, locked)
                reservation = session.execute(
                    select(AuthLoginThrottleReservation)
                    .where(
                        AuthLoginThrottleReservation.reservation_hash
                        == self._reservation_hash(lease.reservation_token)
                    )
                    .with_for_update()
                ).scalar_one_or_none()
                if reservation is None:
                    raise AuthRateLimitReservationError(
                        "rate-limit reservation is unknown or already completed"
                    )
                if reservation.expires_at <= now:
                    self._remove_reservation(session, reservation, locked.all_rows)
                    return False
                decision = self._complete(locked.current, now, success=success)
                session.delete(reservation)
                return decision

        decision = self._run(operation)
        if decision is None:
            raise AuthRateLimitReservationError("rate-limit reservation expired")
        return decision

    def _reservation_hash(self, token: str) -> str:
        return hmac.new(
            self._hmac_secret,
            f"reservation:{token}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

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
                    raise AuthRateLimitStoreError("persistent auth rate-limit store unavailable") from exc
                sleep(self._retry_delay_seconds * (attempt + 1))
            except (DBAPIError, SQLAlchemyError) as exc:
                raise AuthRateLimitStoreError("persistent auth rate-limit store unavailable") from exc
            except RuntimeError as exc:
                if isinstance(exc, AuthRateLimitStoreError):
                    raise
                raise AuthRateLimitStoreError("persistent auth rate-limit store unavailable") from exc
            finally:
                if session is not None:
                    session.close()
        raise AuthRateLimitStoreError("persistent auth rate-limit store unavailable") from last_error

    @staticmethod
    def _is_sqlite_lock(exc: OperationalError) -> bool:
        message = str(exc).lower()
        return "database is locked" in message or "database table is locked" in message

    def _lock_rows(
        self,
        session: Session,
        account_hash: str,
        ip_hash: str,
        now: int,
    ) -> _LockedThrottleRows:
        expired_reservations = session.execute(
            select(AuthLoginThrottleReservation)
            .where(
                AuthLoginThrottleReservation.expires_at <= now,
                (
                    (AuthLoginThrottleReservation.account_hash == account_hash)
                    | (AuthLoginThrottleReservation.ip_hash == ip_hash)
                ),
            )
            .order_by(AuthLoginThrottleReservation.reservation_hash)
            .with_for_update()
        ).scalars().all()
        keys = {
            ("account", account_hash),
            ("ip", ip_hash),
            *(
                (scope, key_hash)
                for reservation in expired_reservations
                for scope, key_hash in (
                    ("account", reservation.account_hash),
                    ("ip", reservation.ip_hash),
                )
            ),
        }
        values = tuple(
            sorted(
                keys,
                key=lambda item: (0 if item[0] == "account" else 1, item[1]),
            )
        )
        for scope, key_hash in values:
            session.execute(
                text(
                    """
                    INSERT INTO auth_login_throttles
                        (scope, key_hash, failure_count, in_flight_count, window_started_at, updated_at)
                    VALUES (:scope, :key_hash, 0, 0, :window_started_at, :updated_at)
                    ON CONFLICT (scope, key_hash) DO NOTHING
                    """
                ),
                {
                    "scope": scope,
                    "key_hash": key_hash,
                    "window_started_at": now,
                    "updated_at": _utc_now(),
                },
            )

        rows: dict[tuple[str, str], AuthLoginThrottle] = {}
        for scope, key_hash in values:
            # The no-op UPDATE acquires SQLite's write lock; FOR UPDATE adds
            # row locking on PostgreSQL. Both operations use account-before-ip order.
            session.execute(
                text(
                    """
                    UPDATE auth_login_throttles
                    SET updated_at = :updated_at
                    WHERE scope = :scope AND key_hash = :key_hash
                    """
                ),
                {"scope": scope, "key_hash": key_hash, "updated_at": _utc_now()},
            )
            row = session.execute(
                select(AuthLoginThrottle)
                .where(
                    AuthLoginThrottle.scope == scope,
                    AuthLoginThrottle.key_hash == key_hash,
                )
                .with_for_update()
            ).scalar_one()
            rows[(scope, key_hash)] = row
        return _LockedThrottleRows(
            current={
                "account": rows[("account", account_hash)],
                "ip": rows[("ip", ip_hash)],
            },
            all_rows=rows,
            expired_reservations=tuple(expired_reservations),
        )

    def _reclaim_expired_reservations(
        self,
        session: Session,
        locked: _LockedThrottleRows,
    ) -> None:
        for reservation in locked.expired_reservations:
            self._remove_reservation(session, reservation, locked.all_rows)

    @staticmethod
    def _remove_reservation(
        session: Session,
        reservation: AuthLoginThrottleReservation,
        rows: dict[tuple[str, str], AuthLoginThrottle],
    ) -> None:
        account_row = rows[("account", reservation.account_hash)]
        ip_row = rows[("ip", reservation.ip_hash)]
        for row in (account_row, ip_row):
            if row.in_flight_count <= 0:
                raise AuthRateLimitStoreError("rate-limit reservation counter invariant violated")
            row.in_flight_count -= 1
            row.updated_at = _utc_now()
        session.delete(reservation)

    def _reserve(
        self,
        rows: dict[str, AuthLoginThrottle],
        now: int,
    ) -> AuthRateLimitDecision:
        for scope, row in rows.items():
            self._roll_window_forward(row, now, self._policies[scope])
            if row.locked_until is not None and row.locked_until > now:
                return AuthRateLimitDecision(
                    allowed=False,
                    retry_after=max(1, row.locked_until - now),
                    scope=scope,
                )
            policy = self._policies[scope]
            if row.failure_count + row.in_flight_count >= policy.max_failures:
                row.locked_until = now + policy.lock_seconds
                row.updated_at = _utc_now()
                return AuthRateLimitDecision(
                    allowed=False,
                    retry_after=policy.lock_seconds,
                    scope=scope,
                )

        for row in rows.values():
            row.in_flight_count += 1
            row.updated_at = _utc_now()
        return AuthRateLimitDecision(allowed=True)

    def _complete(
        self,
        rows: dict[str, AuthLoginThrottle],
        now: int,
        *,
        success: bool,
    ) -> AuthRateLimitDecision:
        lock_decision: AuthRateLimitDecision | None = None
        for scope, row in rows.items():
            policy = self._policies[scope]
            if row.in_flight_count <= 0:
                raise AuthRateLimitStoreError("rate-limit reservation counter invariant violated")
            row.in_flight_count -= 1
            self._roll_window_forward(row, now, policy)
            if success:
                if scope == "account" and row.in_flight_count == 0:
                    row.failure_count = 0
                    row.locked_until = None
                row.updated_at = _utc_now()
                continue
            row.failure_count += 1
            if row.failure_count >= policy.max_failures:
                row.locked_until = max(row.locked_until or 0, now + policy.lock_seconds)
            row.updated_at = _utc_now()
            if lock_decision is None and row.locked_until is not None and row.locked_until > now:
                lock_decision = AuthRateLimitDecision(
                    allowed=False,
                    retry_after=max(1, row.locked_until - now),
                    scope=scope,
                )
        return lock_decision or AuthRateLimitDecision(allowed=True)

    @staticmethod
    def _roll_window_forward(
        row: AuthLoginThrottle,
        now: int,
        policy: AuthRateLimitPolicy,
    ) -> None:
        if row.locked_until is not None and row.locked_until <= now:
            row.locked_until = None
            row.failure_count = 0
        if row.window_started_at <= 0:
            row.window_started_at = now
            return
        if now - row.window_started_at >= policy.window_seconds:
            row.window_started_at = now
            row.failure_count = 0
            # A future lock and valid in-flight reservations are independent
            # of the failure window and must survive the rollover.
