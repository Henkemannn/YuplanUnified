import io
import uuid

from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Dish, Menu, MenuVariant, Tenant, User


def _bootstrap(db):
    t = Tenant(name="ImpT_" + uuid.uuid4().hex[:6])
    db.add(t)
    db.flush()
    u = User(
        tenant_id=t.id,
        email=f"admin_{uuid.uuid4().hex[:6]}@ex.com",
        password_hash=generate_password_hash("pw"),
        role="admin",
        unit_id=None,
    )
    db.add(u)
    db.commit()
    return t, u


def _login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": "pw"})
    assert r.status_code == 200


def test_menu_import_dry_run(monkeypatch, tmp_path):
    from core import db as core_db  # type: ignore

    core_db._engine = None  # type: ignore
    core_db._SessionFactory = None  # type: ignore
    db_file = tmp_path / "dryrun.db"
    db_url = f"sqlite:///{db_file}"
    app = create_app({"database_url": db_url, "secret_key": "x"})
    engine = core_db.init_engine(db_url)  # type: ignore
    from core.models import Base

    Base.metadata.create_all(engine)
    from core.importers.base import ImportedMenuItem, MenuImportResult, WeekImport

    client = app.test_client()
    db = get_session()
    t, u = _bootstrap(db)
    email = u.email
    db.close()
    _login(client, email)

    class DummyImporter:
        def parse(self, data, filename, mime):
            items = [
                ImportedMenuItem(
                    day="monday", meal="lunch", variant_type="alt1", dish_name="Chili"
                ),
                ImportedMenuItem(
                    day="monday", meal="lunch", variant_type="alt2", dish_name="Pasta"
                ),
                ImportedMenuItem(
                    day="tuesday", meal="lunch", variant_type="alt1", dish_name="Chili"
                ),
            ]
            return MenuImportResult(
                weeks=[WeekImport(week=40, year=2025, items=items)], errors=[], warnings=[]
            )

    import core.import_api as import_api_mod

    import_api_mod._importer = DummyImporter()

    data = io.BytesIO(b"placeholder")
    resp = client.post("/import/menu?dry_run=1", data={"file": (data, "menu.xlsx")})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["dry_run"] is True
    diff = body["diff"]
    assert len(diff) == 3
    actions = {(d["day"], d["variant_type"]): d["variant_action"] for d in diff}
    assert actions[("monday", "alt1")] == "create"
    assert actions[("monday", "alt2")] == "create"
    assert actions[("tuesday", "alt1")] == "create"

    db2 = get_session()
    try:
        assert db2.query(Menu).count() == 0
        assert db2.query(MenuVariant).count() == 0
        assert db2.query(Dish).count() == 0
    finally:
        db2.close()
