from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from core.app_factory import create_app


def _build_app(tmp_path: Path, *, env: str = "testing"):
    db_path = tmp_path / "demo_seed.db"
    builder_db_path = tmp_path / "demo_builder.db"
    app = create_app(
        {
            "TESTING": env == "testing",
            "ENV": env,
            "APP_ENV": env,
            "SECRET_KEY": "test-secret-key-0123456789abcdef0123456789abcdef",
            "JWT_SECRET": "test-jwt-secret-0123456789abcdef0123456789abcdef",
            "database_url": f"sqlite:///{db_path}",
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )
    with app.app_context():
        from core.db import create_all

        create_all()
    return app


def _count_rows(table: str, where_sql: str = "", params: dict[str, object] | None = None) -> int:
    from core.db import get_session

    db = get_session()
    try:
        sql = f"SELECT COUNT(*) FROM {table}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        row = db.execute(text(sql), params or {}).fetchone()
        return int(row[0] or 0) if row else 0
    finally:
        db.close()


def test_offshore_demo_seed_cli_creates_idempotent_demo_rows(tmp_path: Path) -> None:
    app = _build_app(tmp_path)
    runner = app.test_cli_runner()

    first = runner.invoke(args=["offshore-demo-seed"])
    assert first.exit_code == 0, first.output
    assert "tenant=9001" in first.output
    assert "site=demo-offshore" in first.output
    assert "prep_tasks=" in first.output

    second = runner.invoke(args=["offshore-demo-seed"])
    assert second.exit_code == 0, second.output

    with app.app_context():
        assert _count_rows("tenants", "id = :id", {"id": 9001}) == 1
        assert _count_rows("sites", "id = :id AND tenant_id = :tenant_id", {"id": "demo-offshore", "tenant_id": 9001}) == 1
        assert _count_rows("offshore_installation_settings", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 1
        assert _count_rows("offshore_work_positions", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 3
        assert _count_rows("offshore_menu_cycles", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 1
        assert _count_rows("offshore_period_templates", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 1
        assert _count_rows("offshore_work_periods", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 1
        assert _count_rows("offshore_service_events", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 6
        assert _count_rows("offshore_service_event_menu_contexts", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 6
        assert _count_rows("offshore_prep_tasks", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 6
        assert _count_rows("commun_builder_menu_links", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 1
        assert _count_rows("commun_builder_publication_pins", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 1


def test_offshore_demo_seed_cli_refuses_in_production(tmp_path: Path) -> None:
    app = _build_app(tmp_path, env="production")
    runner = app.test_cli_runner()

    result = runner.invoke(args=["offshore-demo-seed"])
    assert result.exit_code != 0
    assert "refusing to seed" in result.output
