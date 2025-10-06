from datetime import UTC, datetime, timedelta

from core.audit_repo import AuditQueryFilters, AuditRepo
from core.db import get_session
from core.models import AuditEvent


def _clear():
    db = get_session()
    try:
        db.query(AuditEvent).delete()
        db.commit()
    finally:
        db.close()


def _add(ts, tenant_id=None, event="evt", payload=None, actor_role="admin"):
    db = get_session()
    try:
        ae = AuditEvent(ts=ts, tenant_id=tenant_id, event=event, payload=payload, actor_role=actor_role)
        db.add(ae)
        db.commit()
        return ae.id
    finally:
        db.close()


def test_query_order_desc(app_session):
    _clear()
    now = datetime.now(UTC)
    _add(now - timedelta(seconds=30), tenant_id=1, event="a")
    _add(now - timedelta(seconds=20), tenant_id=1, event="b")
    newest_id = _add(now - timedelta(seconds=10), tenant_id=1, event="c")
    repo = AuditRepo()
    rows, total = repo.query(AuditQueryFilters(), page=1, size=10)
    assert total == 3
    assert [r.event for r in rows] == ["c", "b", "a"]
    assert rows[0].id == newest_id


def test_filter_tenant_and_event(app_session):
    _clear()
    now = datetime.now(UTC)
    _add(now - timedelta(seconds=5), tenant_id=1, event="x")
    target_id = _add(now - timedelta(seconds=4), tenant_id=2, event="keep")
    _add(now - timedelta(seconds=3), tenant_id=2, event="drop")
    repo = AuditRepo()
    rows, total = repo.query(AuditQueryFilters(tenant_id=2, event="keep"), page=1, size=10)
    assert total == 1
    assert rows[0].id == target_id


def test_time_window_inclusive(app_session):
    _clear()
    base = datetime.now(UTC) - timedelta(minutes=1)
    _add(base + timedelta(seconds=0), tenant_id=1, event="early")
    _add(base + timedelta(seconds=10), tenant_id=1, event="mid")
    _add(base + timedelta(seconds=20), tenant_id=1, event="late")
    repo = AuditRepo()
    # Inclusive window spanning early..late should return all
    rows_all, total_all = repo.query(AuditQueryFilters(ts_from=base, ts_to=base + timedelta(seconds=20)), page=1, size=10)
    assert total_all == 3
    # Narrow window capturing only mid
    rows_mid, total_mid = repo.query(AuditQueryFilters(ts_from=base + timedelta(seconds=10), ts_to=base + timedelta(seconds=10)), page=1, size=10)
    assert total_mid == 1
    assert rows_mid[0].event == "mid"


def test_text_search_case_insensitive(app_session):
    _clear()
    now = datetime.now(UTC)
    _add(now, tenant_id=1, event="a", payload={"detail": "Something Special_Marker_ABC"})
    _add(now, tenant_id=1, event="b", payload={"detail": "nothing"})
    repo = AuditRepo()
    rows, total = repo.query(AuditQueryFilters(text="marker_abc"), page=1, size=10)
    assert total == 1
    assert rows[0].event == "a"


def test_purge_older_than(app_session):
    _clear()
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    recent = now - timedelta(days=2)
    _add(old, tenant_id=1, event="old")
    _add(recent, tenant_id=1, event="recent")
    repo = AuditRepo()
    removed = repo.purge_older_than(7)
    assert removed == 1
    rows, total = repo.query(AuditQueryFilters(), page=1, size=10)
    assert total == 1
    assert rows[0].event == "recent"
