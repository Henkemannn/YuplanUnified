from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy import create_engine

from core.app_factory import create_app
from core.db import get_session
from modules.offshore2.work_menu import _service as work_menu_service
from modules.offshore2.models import OffshoreWorkMenuDecision


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
            "database_url": f"sqlite:///{db_path.as_posix()}",
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )
    with app.app_context():
        from core.db import init_engine
        init_engine(str(app.config["SQLALCHEMY_DATABASE_URI"]), force=True)
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


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


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
        assert _count_rows("offshore_service_events", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 14
        assert _count_rows("offshore_service_event_menu_contexts", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 14
        assert _count_rows("offshore_work_menu_decisions", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 56
        assert _count_rows("offshore_prep_tasks", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 14
        assert _count_rows("commun_builder_menu_links", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 4
        assert _count_rows("commun_builder_publication_pins", "tenant_id = :tenant_id AND site_id = :site_id", {"tenant_id": 9001, "site_id": "demo-offshore"}) == 4


def test_offshore_demo_seed_cli_refuses_in_production(tmp_path: Path) -> None:
    app = _build_app(tmp_path, env="production")
    runner = app.test_cli_runner()

    result = runner.invoke(args=["offshore-demo-seed"])
    assert result.exit_code != 0
    assert "refusing to seed" in result.output


def test_offshore_demo_seed_cli_upgrade_creates_required_linkage_tables(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "head.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    command.upgrade(_alembic_cfg(db_url), "head")

    engine = create_engine(db_url)
    with engine.connect() as conn:
        menu_links = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='commun_builder_menu_links'"))
        publication_pins = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='commun_builder_publication_pins'"))
        assert menu_links.fetchone() is not None
        assert publication_pins.fetchone() is not None


def test_offshore_demo_seed_cli_refuses_head_database_missing_linkage_tables(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "drifted.db"
    builder_db_path = tmp_path / "drifted-builder.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    command.upgrade(_alembic_cfg(db_url), "head")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
        conn.exec_driver_sql("DROP TABLE IF EXISTS commun_builder_menu_links")
        conn.exec_driver_sql("DROP TABLE IF EXISTS commun_builder_publication_pins")
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")

    app = create_app(
        {
            "TESTING": False,
            "ENV": "development",
            "APP_ENV": "development",
            "SECRET_KEY": "test-secret-key-0123456789abcdef0123456789abcdef",
            "JWT_SECRET": "test-jwt-secret-0123456789abcdef0123456789abcdef",
            "database_url": db_url,
            "BUILDER_DB_PATH": str(builder_db_path),
        }
    )
    runner = app.test_cli_runner()

    result = runner.invoke(args=["offshore-demo-seed"])
    assert result.exit_code != 0
    assert "schema-drifted" in result.output
    assert "commun_builder_menu_links" in result.output
    assert "0023_scope_service_addons_by_site" in result.output


def test_offshore_demo_seed_reaches_work_menu_titles(tmp_path: Path) -> None:
    app = _build_app(tmp_path)
    runner = app.test_cli_runner()

    result = runner.invoke(args=["offshore-demo-seed"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        from core.db import get_session
        from modules.offshore2.menu_context import _service as menu_context_service
        from modules.offshore2.models import OffshoreServiceEventMenuContext
        from modules.offshore2.periods import _service as period_service

        db = get_session()
        try:
            contexts = (
                db.query(OffshoreServiceEventMenuContext)
                .filter_by(tenant_id=9001, site_id="demo-offshore")
                .order_by(OffshoreServiceEventMenuContext.service_event_id.asc())
                .all()
            )
            assert contexts
            first_context = contexts[0]
            service_events = period_service.list_service_events(9001, "demo-offshore", int(first_context.work_period_id))
            assert service_events
            menu_context_service.sync_service_event_context(
                tenant_id=9001,
                site_id="demo-offshore",
                work_period_id=int(first_context.work_period_id),
                service_event_id=int(service_events[0].id),
            )
        finally:
            db.close()

        with app.test_request_context(
            "/offshore/work-menu",
            headers={"X-User-Role": "cook", "X-User-Name": "Henrik"},
        ):
            vm = work_menu_service.build_view_model(
                tenant_id=9001,
                site_id="demo-offshore",
                locale="sv",
                theme="system",
                role="cook",
                tenant_name="Demo Offshore",
                site_name="Demo Offshore Site",
            )

    lunch_titles: list[str] = []
    lunch_bridges: dict[str, dict[str, object]] = {}
    for day in vm.get("days", ()):
        for meal in getattr(day, "meals", ()):
            if getattr(meal, "meal_slot", "") != "lunch":
                continue
            for track in getattr(meal, "tracks", ()):
                if getattr(track, "track_key", "") in {"koett", "fisk"}:
                    title = getattr(track, "published_title", None)
                    if title:
                        lunch_titles.append(title)
                    bridge = getattr(track, "builder_bridge", None)
                    if bridge:
                        lunch_bridges[str(getattr(track, "track_key", ""))] = dict(bridge)

    assert any(title == "Pork sweetnsour" for title in lunch_titles)
    assert any(title == "Plukkfisk med purre og bacon" for title in lunch_titles)
    assert lunch_bridges["koett"]["composition_id"] != "demo_offshore_fisk"
    assert int(lunch_bridges["koett"]["component_count"]) >= 1
    assert str(lunch_bridges["koett"]["builder_url"]).startswith("/builder-editor-host?composition_id=")
    assert lunch_bridges["fisk"]["composition_id"] != "demo_offshore_fisk"
    assert int(lunch_bridges["fisk"]["component_count"]) >= 1
    assert str(lunch_bridges["fisk"]["builder_url"]).startswith("/builder-editor-host?composition_id=")


def test_offshore_demo_seed_does_not_invent_fake_builder_ids(tmp_path: Path) -> None:
    app = _build_app(tmp_path)
    runner = app.test_cli_runner()

    result = runner.invoke(args=["offshore-demo-seed"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        db = get_session()
        try:
            rows = (
                db.query(OffshoreWorkMenuDecision.selected_builder_composition_id)
                .filter(OffshoreWorkMenuDecision.tenant_id == 9001)
                .filter(OffshoreWorkMenuDecision.site_id == "demo-offshore")
                .all()
            )
        finally:
            db.close()

    selected_ids = {str(row[0] or "") for row in rows}
    assert "demo_offshore_fisk" not in selected_ids
    assert "demo_offshore_vegetariskt" not in selected_ids
