from __future__ import annotations

import json
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_0043_upgrade_creates_revision_table_and_backfills_existing_pin(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "publication_history.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    command.upgrade(_alembic_cfg(db_url), "0042_add_department_portal_week_submissions")

    engine = create_engine(db_url)
    try:
        snapshot = json.dumps(
            {
                "schema_version": 1,
                "tenant_id": 1,
                "site_id": "site-history",
                "year": 2025,
                "week": 46,
                "builder_menu_id": "builder-menu-history",
                "builder_menu_version": 1,
                "builder_status": "published",
                "projection_version": 1,
                "source": "commun.builder.projection_snapshot_v1",
                "rows": [
                    {
                        "day": "monday",
                        "meal": "lunch",
                        "variant_type": "main",
                        "sort_order": 10,
                        "builder_menu_row_id": "builder-menu-history-row-1",
                        "selection_group_id": "grp_x",
                        "composition_id": "comp_1",
                        "resolved": True,
                        "text": "Soup",
                        "unresolved_text": None,
                        "error": None,
                    }
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO tenants(id, name) VALUES (1, 'Tenant 1')"))
            conn.execute(text("INSERT INTO sites(id, name, version) VALUES ('site-history', 'History Site', 0)"))
            conn.execute(
                text("INSERT INTO menus(id, tenant_id, site_id, week, year, status) VALUES (1, 1, 'site-history', 46, 2025, 'published')")
            )
            conn.execute(
                text(
                    "INSERT INTO commun_builder_publication_pins("
                    "id, tenant_id, site_id, year, week, legacy_menu_id, builder_menu_id, builder_menu_version, source, projection_snapshot_json, created_at, updated_at"
                    ") VALUES (:id, 1, 'site-history', 2025, 46, 1, 'builder-menu-history', 1, 'manual', :snapshot, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": str(uuid.uuid4()), "snapshot": snapshot},
            )

        command.upgrade(_alembic_cfg(db_url), "0043_add_commun_builder_publication_revisions")

        inspector = inspect(engine)
        assert "commun_builder_publication_revisions" in inspector.get_table_names()

        with engine.begin() as conn:
            pin_row = conn.execute(
                text(
                    "SELECT builder_menu_version, projection_snapshot_json FROM commun_builder_publication_pins "
                    "WHERE tenant_id=1 AND site_id='site-history' AND year=2025 AND week=46"
                )
            ).fetchone()
            revision_row = conn.execute(
                text(
                    "SELECT builder_menu_version, projection_snapshot_json FROM commun_builder_publication_revisions "
                    "WHERE tenant_id=1 AND site_id='site-history' AND year=2025 AND week=46"
                )
            ).fetchone()
            alembic_row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()

        assert pin_row is not None
        assert int(pin_row[0]) == 1
        assert revision_row is not None
        assert int(revision_row[0]) == 1
        assert '"selection_group_id":"grp_x"' in str(revision_row[1])
        assert str(revision_row[1]) == snapshot
        assert alembic_row is not None
        assert str(alembic_row[0]) == "0043_add_commun_builder_publication_revisions"
    finally:
        engine.dispose()
