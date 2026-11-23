import gc
from pathlib import Path
import shutil
import tempfile
import uuid

import pytest
from flask import Flask
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session, init_engine
from core.models import Base, Note, Site, Task, Tenant, User


@pytest.fixture()
def app(request):
    state = request.config._yuplan_test_db_state
    isolated_root = Path(tempfile.mkdtemp(prefix="yuplan-export-"))
    isolated_db = isolated_root / "main.db"
    isolated_builder_db = isolated_root / "builder.db"
    original_db_url = f"sqlite:///{state['main_db'].as_posix()}"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": f"sqlite:///{isolated_db.as_posix()}",
            "BUILDER_DB_PATH": str(isolated_builder_db),
            "FORCE_DB_REINIT": True,
        }
    )
    db = get_session()
    try:
        engine = db.get_bind()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        db.execute(
            text(
                "CREATE TABLE kitchen_user_sites "
                "(user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        db.commit()
        yield app
    finally:
        db.close()
        from core import db as db_mod

        if db_mod._SessionFactory is not None:
            db_mod._SessionFactory.remove()
        if db_mod._engine is not None:
            db_mod._engine.dispose(close=True)
        db_mod._SessionFactory = None
        db_mod._engine = None
        init_engine(original_db_url, force=True)
        gc.collect()
        shutil.rmtree(isolated_root)


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def seeded(client):
    db = get_session()
    try:
        tenant = Tenant(name=f"ExportT-{uuid.uuid4().hex}")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        # Clean possible previous runs
        db.query(Note).delete()
        db.query(Task).delete()
        db.query(User).filter(
            User.email.in_(["exp_admin@example.com", "exp_cook@example.com"])
        ).delete()
        db.commit()
        tenant_b = Tenant(name=f"Export Other Tenant {uuid.uuid4().hex}")
        db.add(tenant_b)
        db.flush()
        site_a = Site(id=f"export-site-a-{uuid.uuid4().hex}", tenant_id=tenant.id, name="Export Site A")
        site_b = Site(id=f"export-site-b-{uuid.uuid4().hex}", tenant_id=tenant.id, name="Export Site B")
        site_c = Site(id=f"export-site-c-{uuid.uuid4().hex}", tenant_id=tenant_b.id, name="Export Site C")
        db.add_all([site_a, site_b, site_c])
        db.flush()
        admin = User(
            tenant_id=tenant.id,
            email="exp_admin@example.com",
            password_hash=generate_password_hash("pw"),
            role="admin",
            unit_id=None,
        )
        cook = User(
            tenant_id=tenant.id,
            email="exp_cook@example.com",
            password_hash=generate_password_hash("pw"),
            role="cook",
            unit_id=None,
        )
        db.add_all([admin, cook])
        db.commit()
        db.refresh(admin)
        db.refresh(cook)
        tenant_id = int(tenant.id)
        admin_id = int(admin.id)
        cook_id = int(cook.id)
        # Seed some data
        n1 = Note(
            tenant_id=tenant.id,
            site_id=site_a.id,
            user_id=admin.id,
            content="Public Note",
            private_flag=False,
        )
        n2 = Note(
            tenant_id=tenant.id,
            site_id=site_a.id,
            user_id=admin.id,
            content="Privat Note",
            private_flag=True,
        )
        n3 = Note(
            tenant_id=tenant.id,
            site_id=site_b.id,
            user_id=admin.id,
            content="Other Site Note",
            private_flag=False,
        )
        n4 = Note(
            tenant_id=tenant.id,
            site_id=site_b.id,
            user_id=admin.id,
            content="Other Site Private Note",
            private_flag=True,
        )
        n5 = Note(
            tenant_id=tenant_b.id,
            site_id=site_c.id,
            user_id=admin.id,
            content="Other Tenant Note",
            private_flag=False,
        )
        n6 = Note(
            tenant_id=tenant.id,
            site_id=None,
            user_id=admin.id,
            content="Unscoped Note",
            private_flag=False,
        )
        db.add_all([n1, n2, n3, n4, n5, n6])
        db.commit()
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, :tenant_id, :site_id)"
            ),
            {"user_id": admin.id, "tenant_id": tenant.id, "site_id": site_a.id},
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (:user_id, :tenant_id, :site_id)"
            ),
            {"user_id": cook.id, "tenant_id": tenant.id, "site_id": site_a.id},
        )
        db.commit()
        t1 = Task(
            tenant_id=tenant.id,
            unit_id=None,
            task_type="prep",
            title="Hacka lök",
            done=False,
            private_flag=False,
        )
        t2 = Task(
            tenant_id=tenant.id,
            unit_id=None,
            task_type="prep",
            title="Privat staging",
            done=True,
            private_flag=True,
            creator_user_id=admin.id,
        )
        db.add_all([t1, t2])
        db.commit()
        site_id = site_a.id
        # Return primitive IDs to avoid DetachedInstance issues once session closed
        return {
            "tenant_id": tenant_id,
            "admin_id": admin_id,
            "cook_id": cook_id,
            "site_id": site_id,
            "other_site_id": site_b.id,
        }
    finally:
        db.close()


def login(client, email, site_id: str = "test-site"):
    # Seed session site binding to satisfy strict site isolation
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
    return client.post("/auth/login", json={"email": email, "password": "pw"})


def test_export_requires_admin_role(client, seeded):
    # login as cook (not admin)
    assert login(client, "exp_cook@example.com", seeded["site_id"]).status_code == 200
    rv = client.get("/export/notes.csv")
    assert rv.status_code in (403, 401)


def test_export_notes_csv_basic(client, seeded):
    assert login(client, "exp_admin@example.com", seeded["site_id"]).status_code == 200
    rv = client.get("/export/notes.csv")
    assert rv.status_code == 200
    assert rv.headers["Content-Type"].startswith("text/csv")
    body = rv.get_data(as_text=True)
    # header + both notes (private still included because admin)
    assert "Public Note" in body and "Privat Note" in body
    assert "Other Site Note" not in body
    assert "Other Site Private Note" not in body
    assert "Other Tenant Note" not in body
    assert "Unscoped Note" not in body
    assert body.splitlines()[0].startswith("id,created_at")


def test_export_notes_requires_bound_site_and_preserves_csv_options(client, seeded):
    assert login(client, "exp_admin@example.com", seeded["site_id"]).status_code == 200
    rv = client.get("/export/notes.csv?sep=;&bom=1")
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    assert body.startswith("\ufeff")
    assert ";" in body.splitlines()[0]

    with client.session_transaction() as session:
        session.pop("site_id", None)
    rv = client.get("/export/notes.csv")
    assert rv.status_code in (401, 403)


def test_export_notes_rejects_site_switch_and_missing_binding(client, seeded):
    assert login(client, "exp_admin@example.com", seeded["site_id"]).status_code == 200

    with client.session_transaction() as session:
        session["site_id"] = seeded["other_site_id"]
    rv = client.get("/export/notes.csv")
    assert rv.status_code in (401, 403)
    assert "Other Site Note" not in rv.get_data(as_text=True)

    db = get_session()
    try:
        db.execute(
            text(
                "DELETE FROM kitchen_user_sites "
                "WHERE user_id = :user_id AND tenant_id = :tenant_id"
            ),
            {"user_id": seeded["admin_id"], "tenant_id": seeded["tenant_id"]},
        )
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as session:
        session["site_id"] = seeded["site_id"]
    rv = client.get("/export/notes.csv")
    assert rv.status_code in (401, 403)


def test_export_tasks_csv_separator_and_bom(client, seeded):
    assert login(client, "exp_admin@example.com", seeded["site_id"]).status_code == 200
    rv = client.get("/export/tasks.csv?sep=;&bom=1")
    assert rv.status_code == 404
    assert "Public Note" not in rv.get_data(as_text=True)


def test_export_streaming_large(client, seeded):
    # Add a few more rows to exercise generator (not a strict performance test)
    db = get_session()
    try:
        for i in range(5):
            db.add(
                Note(
                    tenant_id=seeded["tenant_id"],
                    site_id=seeded["site_id"],
                    user_id=seeded["admin_id"],
                    content=f"Extra {i}",
                    private_flag=False,
                )
            )
        db.commit()
    finally:
        db.close()
    assert login(client, "exp_admin@example.com", seeded["site_id"]).status_code == 200
    rv = client.get("/export/notes.csv")
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    # confirm at least 1 of the extra rows
    assert "Extra 0" in body
