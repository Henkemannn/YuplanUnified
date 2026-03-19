from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.admin_repo import ServiceAddonsRepo, SitesRepo
from core.db import get_session


def test_service_addons_unique_scoped_by_site(app_session):
    site_a, _ = SitesRepo().create_site(f"Addon site A {uuid.uuid4()}")
    site_b, _ = SitesRepo().create_site(f"Addon site B {uuid.uuid4()}")
    site_c, _ = SitesRepo().create_site(f"Addon site C {uuid.uuid4()}")

    repo = ServiceAddonsRepo()
    a_id = repo.create_if_missing("Mos", site_id=site_a["id"], addon_family="mos")
    b_id = repo.create_if_missing("Mos", site_id=site_b["id"], addon_family="mos")

    assert a_id != b_id

    # Same-site duplicate should not create another row.
    a_id_again = repo.create_if_missing("Mos", site_id=site_a["id"], addon_family="mos")
    assert a_id_again == a_id

    db = get_session()
    try:
        ddl_row = db.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='service_addons'")
        ).fetchone()
        ddl = str((ddl_row[0] if ddl_row else "") or "")
        ddl_norm = ddl.replace(" ", "").lower()
        assert "unique(site_id,name)" in ddl_norm
        assert "unique(name)" not in ddl_norm

        # DB-level uniqueness check: duplicate name within same site should fail.
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    """
                    INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at)
                    VALUES(:id, :site_id, :name, :addon_family, 1, CURRENT_TIMESTAMP)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "site_id": site_a["id"],
                    "name": "Mos",
                    "addon_family": "mos",
                },
            )
            db.commit()
        db.rollback()

        # Same name for another site should be allowed.
        db.execute(
            text(
                """
                INSERT INTO service_addons(id, site_id, name, addon_family, is_active, created_at)
                VALUES(:id, :site_id, :name, :addon_family, 1, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "site_id": site_c["id"],
                "name": "Mos",
                "addon_family": "mos",
            },
        )
        db.commit()
    finally:
        db.close()
