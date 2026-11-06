from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from core.auth_rate_limit import (
    AuthLoginRateLimitStore,
    AuthRateLimitPolicy,
    AuthRateLimitReservationError,
    AuthRateLimitStoreError,
)
from core.models import AuthLoginThrottle, AuthLoginThrottleReservation, Base


def _make_store(db_path: Path, clock, *, max_retries: int = 8) -> AuthLoginRateLimitStore:
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"timeout": 0.2},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return AuthLoginRateLimitStore(
        factory,
        hmac_secret="test-only-rate-limit-secret",
        account_policy=AuthRateLimitPolicy(300, 5, 600),
        ip_policy=AuthRateLimitPolicy(300, 100, 60),
        max_retries=max_retries,
        retry_delay_seconds=0.01,
        clock=clock,
    )


def test_account_counter_lock_and_expiry_use_only_hmac_keys(tmp_path: Path) -> None:
    now = [1_000]
    store = _make_store(tmp_path / "throttle.db", lambda: now[0])

    for _ in range(5):
        decision, lease = store.begin_attempt("Resident@Example.com", "192.0.2.10")
        assert decision.allowed
        store.complete_attempt(lease, success=False)

    decision, lease = store.begin_attempt("resident@example.com", "192.0.2.11")
    assert not decision.allowed
    assert decision.scope == "account"
    assert decision.retry_after == 600
    assert not lease.allowed

    now[0] += 901
    decision, lease = store.begin_attempt("resident@example.com", "192.0.2.11")
    assert decision.allowed
    store.complete_attempt(lease, success=True)

    session = store._session_factory()
    try:
        rows = session.execute(select(AuthLoginThrottle)).scalars().all()
        assert len(rows) == 3
        assert all("resident@example.com" not in row.key_hash for row in rows)
        assert all("192.0.2." not in row.key_hash for row in rows)
    finally:
        session.close()


def test_future_lock_survives_failure_window_rollover(tmp_path: Path) -> None:
    now = [1_000]
    store = _make_store(tmp_path / "future-lock.db", lambda: now[0])

    for _ in range(5):
        decision, lease = store.begin_attempt("locked@example.com", "192.0.2.40")
        assert decision.allowed
        store.complete_attempt(lease, success=False)

    now[0] = 1_301
    decision, lease = store.begin_attempt("locked@example.com", "192.0.2.41")
    assert not decision.allowed
    assert decision.scope == "account"
    assert decision.retry_after == 299
    assert not lease.allowed


def test_in_flight_reservation_survives_failure_window_rollover(tmp_path: Path) -> None:
    now = [1_299]
    store = _make_store(tmp_path / "boundary-reservation.db", lambda: now[0])

    decision, original = store.begin_attempt("boundary@example.com", "192.0.2.42")
    assert decision.allowed
    now[0] = 1_300
    decision, newer = store.begin_attempt("boundary@example.com", "192.0.2.43")
    assert decision.allowed

    store.complete_attempt(original, success=True)
    store.complete_attempt(newer, success=False)

    session = store._session_factory()
    try:
        account = session.execute(
            select(AuthLoginThrottle).where(AuthLoginThrottle.scope == "account")
        ).scalar_one()
        assert account.in_flight_count == 0
        assert account.failure_count == 1
    finally:
        session.close()


@pytest.mark.parametrize("scenario", ["different_ip", "different_account"])
def test_expired_reservation_reclaims_every_affected_row(
    tmp_path: Path,
    scenario: str,
) -> None:
    now = [1_000]
    store = _make_store(tmp_path / f"reclaim-{scenario}.db", lambda: now[0])
    decision, abandoned = store.begin_attempt("old@example.com", "192.0.2.44")
    assert decision.allowed
    now[0] = 1_031

    if scenario == "different_ip":
        decision, replacement = store.begin_attempt("old@example.com", "192.0.2.45")
    else:
        decision, replacement = store.begin_attempt("new@example.com", "192.0.2.44")
    assert decision.allowed
    store.complete_attempt(replacement, success=True)

    session = store._session_factory()
    try:
        rows = session.execute(select(AuthLoginThrottle)).scalars().all()
        assert all(row.in_flight_count == 0 for row in rows)
        reservations = session.execute(select(AuthLoginThrottleReservation)).scalars().all()
        assert reservations == []
    finally:
        session.close()

    with pytest.raises(AuthRateLimitReservationError):
        store.complete_attempt(abandoned, success=False)


def test_accounts_share_ip_without_sharing_account_lock(tmp_path: Path) -> None:
    store = _make_store(tmp_path / "shared-ip.db", lambda: 1_000)

    for email in ("one@example.com", "two@example.com"):
        decision, lease = store.begin_attempt(email, "198.51.100.10")
        assert decision.allowed
        store.complete_attempt(lease, success=False)

    session = store._session_factory()
    try:
        rows = session.execute(select(AuthLoginThrottle)).scalars().all()
        assert sum(row.scope == "account" for row in rows) == 2
        assert sum(row.scope == "ip" for row in rows) == 1
        assert sorted(
            row.failure_count for row in rows if row.scope == "account"
        ) == [1, 1]
        assert next(row.failure_count for row in rows if row.scope == "ip") == 2
    finally:
        session.close()


def test_abandoned_reservation_is_reclaimed_after_ttl(tmp_path: Path) -> None:
    now = [1_000]
    store = _make_store(tmp_path / "reservation-expiry.db", lambda: now[0])

    decision, abandoned = store.begin_attempt("abandoned@example.com", "192.0.2.20")
    assert decision.allowed

    now[0] += 31
    decision, replacement = store.begin_attempt("abandoned@example.com", "192.0.2.20")
    assert decision.allowed
    store.complete_attempt(replacement, success=True)

    session = store._session_factory()
    try:
        assert session.execute(select(AuthLoginThrottleReservation)).scalars().all() == []
        account = session.execute(
            select(AuthLoginThrottle).where(AuthLoginThrottle.scope == "account")
        ).scalar_one()
        assert account.in_flight_count == 0
    finally:
        session.close()

    with pytest.raises(AuthRateLimitReservationError):
        store.complete_attempt(abandoned, success=False)


def test_completion_is_single_use_and_does_not_release_other_attempt(tmp_path: Path) -> None:
    store = _make_store(tmp_path / "single-use.db", lambda: 1_000)

    first_decision, first = store.begin_attempt("same@example.com", "192.0.2.21")
    second_decision, second = store.begin_attempt("same@example.com", "192.0.2.22")
    assert first_decision.allowed and second_decision.allowed

    store.complete_attempt(first, success=True)
    with pytest.raises(AuthRateLimitReservationError):
        store.complete_attempt(first, success=True)

    session = store._session_factory()
    try:
        account = session.execute(
            select(AuthLoginThrottle).where(AuthLoginThrottle.scope == "account")
        ).scalar_one()
        assert account.in_flight_count == 1
        assert account.failure_count == 0
    finally:
        session.close()

    store.complete_attempt(second, success=False)


def test_success_does_not_clear_shared_ip_failures(tmp_path: Path) -> None:
    store = _make_store(tmp_path / "shared-ip-success.db", lambda: 1_000)

    failed_decision, failed = store.begin_attempt("failed@example.com", "192.0.2.30")
    assert failed_decision.allowed
    store.complete_attempt(failed, success=False)

    success_decision, success = store.begin_attempt("success@example.com", "192.0.2.30")
    assert success_decision.allowed
    store.complete_attempt(success, success=True)

    session = store._session_factory()
    try:
        rows = session.execute(select(AuthLoginThrottle)).scalars().all()
        account_rows = {row.key_hash: row for row in rows if row.scope == "account"}
        ip_row = next(row for row in rows if row.scope == "ip")
        assert ip_row.failure_count == 1
        assert any(row.failure_count == 1 for row in account_rows.values())
        assert any(row.failure_count == 0 for row in account_rows.values())
    finally:
        session.close()


def test_concurrent_processes_do_not_lose_failures(tmp_path: Path) -> None:
    db_path = tmp_path / "concurrent.db"
    store = _make_store(db_path, lambda: 1_000)
    del store
    context = get_context("spawn")
    barrier = context.Barrier(8)
    queue = context.Queue()
    processes = [
        context.Process(target=_record_failure_worker, args=(str(db_path), barrier, queue))
        for _ in range(8)
    ]
    for process in processes:
        process.start()
    results = [queue.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0

    assert sum(results) == 5
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        with sessionmaker(bind=engine)() as session:
            account = session.execute(
                select(AuthLoginThrottle).where(AuthLoginThrottle.scope == "account")
            ).scalar_one()
            assert account.failure_count == 5
            assert account.locked_until == 1_600
    finally:
        engine.dispose()


def _record_failure_worker(db_path: str, barrier, queue) -> None:
    store = _make_store(Path(db_path), lambda: 1_000)
    barrier.wait()
    decision, lease = store.begin_attempt("parallel@example.com", "203.0.113.7")
    if decision.allowed:
        store.complete_attempt(lease, success=False)
        queue.put(1)
    else:
        queue.put(0)


def test_database_failure_is_explicit_and_never_falls_back() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    def unavailable_session():
        raise SQLAlchemyError("database unavailable")

    store = AuthLoginRateLimitStore(
        unavailable_session,
        hmac_secret="test-only-rate-limit-secret",
    )
    with pytest.raises(AuthRateLimitStoreError):
        store.begin_attempt("resident@example.com", "192.0.2.10")


def test_auth_login_throttle_migration_up_and_down(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "migration.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(config, "head")
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        assert "auth_login_throttles" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("auth_login_throttles")}
        assert {
            "scope",
            "key_hash",
            "failure_count",
            "in_flight_count",
            "window_started_at",
            "locked_until",
            "updated_at",
        } <= columns
        assert "uq_auth_login_throttles_scope_key" in {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("auth_login_throttles")
        }
        assert "auth_login_throttle_reservations" in inspector.get_table_names()
    finally:
        engine.dispose()

    command.downgrade(config, "0047_add_service_addon_scope_quantity_mode")
    engine = create_engine(db_url)
    try:
        assert "auth_login_throttles" not in inspect(engine).get_table_names()
        assert "auth_login_throttle_reservations" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
