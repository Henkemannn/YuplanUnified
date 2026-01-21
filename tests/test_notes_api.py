from contextlib import suppress

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Tenant, User


@pytest.fixture()
def app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    return app


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


@pytest.fixture()
def seeded_users():
    db = get_session()
    try:
        # Ensure schema exists (in case migrations not executed in test context)
        with suppress(Exception):
            create_all()
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="T1")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        # Clean prior test runs for idempotency when reusing same SQLite DB
        db.query(User).filter(User.email.in_(["u1@example.com", "u2@example.com"])).delete(
            synchronize_session=False
        )
        db.commit()
        # creator user
        u1 = User(
            tenant_id=tenant.id,
            email="u1@example.com",
            password_hash=generate_password_hash("pw"),
            role="admin",
            unit_id=None,
        )
        u2 = User(
            tenant_id=tenant.id,
            email="u2@example.com",
            password_hash=generate_password_hash("pw"),
            role="cook",
            unit_id=None,
        )
        db.add_all([u1, u2])
        db.commit()
        db.refresh(u1)
        db.refresh(u2)
        return {"tenant": tenant, "u1": u1, "u2": u2}
    finally:
        db.close()


def login(client, email, password="pw"):
    # Bind session to a test site to satisfy strict site isolation
    with client.session_transaction() as sess:
        sess["site_id"] = "test-site"
    return client.post("/auth/login", json={"email": email, "password": password})


def test_notes_crud_and_privacy(client, seeded_users):
    # login as u1 (admin)
    rv = login(client, "u1@example.com")
    assert rv.status_code == 200
    # create public note
    rv = client.post("/notes/", json={"content": "Public Note"})
    assert rv.status_code == 200
    note_public = rv.get_json()["note"]
    # create private note
    rv = client.post("/notes/", json={"content": "Secret", "private_flag": True})
    assert rv.status_code == 200
    note_private = rv.get_json()["note"]
    # list notes as author (should see both)
    rv = client.get("/notes/")
    data = rv.get_json()
    assert len(data["notes"]) >= 2
    ids = {n["id"] for n in data["notes"]}
    assert note_public["id"] in ids and note_private["id"] in ids

    # logout and login as cook user u2
    client.post("/auth/logout")
    rv = login(client, "u2@example.com")
    assert rv.status_code == 200
    # list notes as other user (no private)
    rv = client.get("/notes/")
    data = rv.get_json()
    ids = {n["id"] for n in data["notes"]}
    assert note_public["id"] in ids
    assert note_private["id"] not in ids

    # attempt update private note (should fail)
    rv = client.put(f"/notes/{note_private['id']}", json={"content": "Hack"})
    assert rv.status_code == 403

    # update public note (allowed? user2 not owner; only admin/superuser or owner) expect forbidden
    rv = client.put(f"/notes/{note_public['id']}", json={"content": "Changed"})
    assert rv.status_code == 403

    # login back as admin and update
    client.post("/auth/logout")
    rv = login(client, "u1@example.com")
    assert rv.status_code == 200
    rv = client.put(f"/notes/{note_public['id']}", json={"content": "Changed"})
    assert rv.status_code == 200
    assert rv.get_json()["note"]["content"] == "Changed"

    # delete public note
    rv = client.delete(f"/notes/{note_public['id']}")
    assert rv.status_code == 200
    # ensure it's gone
    rv = client.get("/notes/")
    ids_after = {n["id"] for n in rv.get_json()["notes"]}
    assert note_public["id"] not in ids_after
