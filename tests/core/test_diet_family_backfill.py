from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_diet_family_column_backfilled_from_existing_names(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'diet-family.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0019_add_production_lists")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            for name in ("Timbal-Fisk", "Glutenfri", "Vegan", "Special A"):
                conn.execute(
                    text("INSERT INTO dietary_types(tenant_id, name, default_select) VALUES(1, :name, 0)"),
                    {"name": name},
                )
        command.upgrade(config, "0020_add_diet_family_to_dietary_types")
        with engine.connect() as conn:
            by_name = dict(conn.execute(text("SELECT name, diet_family FROM dietary_types")).all())
        assert by_name["Timbal-Fisk"] == "Textur"
        assert by_name["Glutenfri"] == "Allergi / Exkludering"
        assert by_name["Vegan"] == "Kostval"
        assert by_name["Special A"] == "Övrigt"
        command.upgrade(config, "0035_add_dietary_types_requirement_identity")
        canonical_columns = {column["name"] for column in inspect(engine).get_columns("dietary_types")}
        assert {"tenant_id", "site_id", "diet_family", "requirement_key", "semantics"} <= canonical_columns
    finally:
        engine.dispose()


def test_diet_family_utils_normalize_and_infer():
    from core.diet_family import infer_diet_family, normalize_diet_family

    assert normalize_diet_family("allergi") == "Allergi / Exkludering"
    assert normalize_diet_family("Övrigt") == "Övrigt"
    assert normalize_diet_family("unknown") == "Övrigt"

    assert infer_diet_family("Timbal") == "Textur"
    assert infer_diet_family("Ej fisk") == "Allergi / Exkludering"
    assert infer_diet_family("Vegetarisk") == "Kostval"
    assert infer_diet_family("Fri text") == "Övrigt"
