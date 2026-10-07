from __future__ import annotations

from sqlalchemy import text

from scripts.seed_mvp_weekview import DEFAULT_TENANT_ID, FLAG_NAME, ensure_pilot_weekview_enabled


def _flag_rows(db, tenant_id: int):
    return db.execute(
        text("SELECT tenant_id, name, enabled FROM tenant_feature_flags WHERE tenant_id=:tid AND name=:name"),
        {"tid": tenant_id, "name": FLAG_NAME},
    ).fetchall()


def test_mvp_weekview_seed_enables_flag_and_is_idempotent(app_session):
    with app_session.app_context():
        ensure_pilot_weekview_enabled(tenant_id=DEFAULT_TENANT_ID, tenant_name="MVP Test1")
        ensure_pilot_weekview_enabled(tenant_id=DEFAULT_TENANT_ID, tenant_name="MVP Test1")

        from core.db import get_session

        db = get_session()
        try:
            rows = _flag_rows(db, DEFAULT_TENANT_ID)
            assert len(rows) == 1
            assert int(rows[0][2]) == 1
            tenant_count = db.execute(
                text("SELECT COUNT(*) FROM tenants WHERE id=:tid"),
                {"tid": DEFAULT_TENANT_ID},
            ).scalar_one()
            assert int(tenant_count) == 1
        finally:
            db.close()