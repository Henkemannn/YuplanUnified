from sqlalchemy import inspect, text


def _restore_canonical_dietary_types_schema(db) -> None:
    from core.models import DietaryType

    db.execute(text("DROP TABLE IF EXISTS dietary_types"))
    DietaryType.__table__.create(bind=db.bind, checkfirst=True)
    db.commit()


def _canonical_dietary_types_columns(db) -> list[str]:
    inspector = inspect(db.bind)
    return [column["name"] for column in inspector.get_columns("dietary_types")]


def test_diet_family_column_backfilled_from_existing_names(app_session):
    from core.db import get_session
    from core.admin_repo import DietTypesRepo

    db = get_session()
    try:
        db.execute(text("DROP TABLE IF EXISTS dietary_types"))
        db.execute(
            text(
                """
                CREATE TABLE dietary_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id TEXT NULL,
                    name TEXT NOT NULL,
                    default_select INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        db.execute(
            text("INSERT INTO dietary_types(site_id, name, default_select) VALUES('site-1', 'Timbal-Fisk', 0)")
        )
        db.execute(
            text("INSERT INTO dietary_types(site_id, name, default_select) VALUES('site-1', 'Glutenfri', 0)")
        )
        db.execute(
            text("INSERT INTO dietary_types(site_id, name, default_select) VALUES('site-1', 'Vegan', 0)")
        )
        db.execute(
            text("INSERT INTO dietary_types(site_id, name, default_select) VALUES('site-1', 'Special A', 0)")
        )
        db.commit()

        repo = DietTypesRepo()
        rows = repo.list_all(tenant_id=1)
        by_name = {str(r.get("name")): str(r.get("diet_family")) for r in rows}

        assert by_name.get("Timbal-Fisk") == "Textur"
        assert by_name.get("Glutenfri") == "Allergi / Exkludering"
        assert by_name.get("Vegan") == "Kostval"
        assert by_name.get("Special A") == "Övrigt"
    finally:
        try:
            db = get_session()
            _restore_canonical_dietary_types_schema(db)
            canonical_columns = _canonical_dietary_types_columns(db)
        finally:
            db.close()

    assert "tenant_id" in canonical_columns
    assert "site_id" in canonical_columns
    assert "diet_family" in canonical_columns
    assert "requirement_key" in canonical_columns
    assert "semantics" in canonical_columns


def test_diet_family_utils_normalize_and_infer():
    from core.diet_family import infer_diet_family, normalize_diet_family

    assert normalize_diet_family("allergi") == "Allergi / Exkludering"
    assert normalize_diet_family("Övrigt") == "Övrigt"
    assert normalize_diet_family("unknown") == "Övrigt"

    assert infer_diet_family("Timbal") == "Textur"
    assert infer_diet_family("Ej fisk") == "Allergi / Exkludering"
    assert infer_diet_family("Vegetarisk") == "Kostval"
    assert infer_diet_family("Fri text") == "Övrigt"
