from contextlib import suppress

import pytest
from flask import Flask
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.admin_repo import SitesRepo
from core.db import create_all, get_session
from core.models import Note, Tenant, User


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
        db.query(User).filter(
            User.email.in_(["u1@example.com", "u2@example.com", "u3@example.com"])
        ).delete(
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
        tenant_b = db.query(Tenant).filter(Tenant.name == "T2").first()
        if not tenant_b:
            tenant_b = Tenant(name="T2")
            db.add(tenant_b)
            db.flush()
        u3 = User(
            tenant_id=tenant_b.id,
            email="u3@example.com",
            password_hash=generate_password_hash("pw"),
            role="admin",
            unit_id=None,
        )
        db.add_all([u1, u2, u3])
        db.commit()
        tenant_b_id = int(tenant_b.id)
        db.refresh(u1)
        db.refresh(u2)
        db.refresh(u3)
        tenant_id = int(tenant.id)
        site_rows = SitesRepo().list_sites_for_tenant(tenant_id)
        if site_rows:
            site_id = str(site_rows[0].get("id"))
        else:
            site, _ = SitesRepo().create_site("Notes Test Site", tenant_id=tenant_id)
            site_id = str(site.get("id"))
        site_b, _ = SitesRepo().create_site("Notes Other Site", tenant_id=tenant_id)
        site_c, _ = SitesRepo().create_site("Notes Tenant B Site", tenant_id=tenant_b_id)
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL, "
                "PRIMARY KEY (user_id, site_id))"
            )
        )
        for email in ("u1@example.com", "u2@example.com"):
            db.execute(
                text(
                    "INSERT OR REPLACE INTO kitchen_user_sites "
                    "(user_id, tenant_id, site_id) "
                    "SELECT id, :tenant_id, :site_id FROM users WHERE email=:email"
                ),
                {"tenant_id": tenant_id, "site_id": site_id, "email": email},
            )
        db.execute(
            text(
                "INSERT OR REPLACE INTO kitchen_user_sites "
                "(user_id, tenant_id, site_id) "
                "SELECT id, :tenant_id, :site_id FROM users WHERE email=:email"
            ),
            {
                "tenant_id": tenant_b_id,
                "site_id": str(site_c.get("id")),
                "email": "u3@example.com",
            },
        )
        db.commit()
        return {
            "tenant_id": tenant_id,
            "u1_email": "u1@example.com",
            "u2_email": "u2@example.com",
            "site_id": site_id,
            "site_b_id": str(site_b.get("id")),
            "site_c_id": str(site_c.get("id")),
            "u3_email": "u3@example.com",
            "u1_id": int(u1.id),
            "u3_id": int(u3.id),
            "tenant_b_id": tenant_b_id,
        }
    finally:
        db.close()


def login(client, email, site_id, password="pw"):
    # Bind session to a test site to satisfy strict site isolation
    with client.session_transaction() as sess:
        sess["site_id"] = str(site_id)
    return client.post("/auth/login", json={"email": email, "password": password})


def test_notes_crud_and_privacy(client, seeded_users):
    # login as u1 (admin)
    rv = login(client, seeded_users["u1_email"], seeded_users["site_id"])
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
    rv = login(client, seeded_users["u2_email"], seeded_users["site_id"])
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
    rv = login(client, seeded_users["u1_email"], seeded_users["site_id"])
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


def test_notes_are_site_scoped_and_rejected_writes_are_unchanged(
    app, client, seeded_users
):
    db = get_session()
    try:
        note_a = Note(
            tenant_id=seeded_users["tenant_id"],
            site_id=seeded_users["site_id"],
            user_id=seeded_users["u1_id"],
            content="Site A",
            private_flag=False,
        )
        note_b = Note(
            tenant_id=seeded_users["tenant_id"],
            site_id=seeded_users["site_b_id"],
            user_id=seeded_users["u1_id"],
            content="Site B",
            private_flag=False,
        )
        note_c = Note(
            tenant_id=seeded_users["tenant_b_id"],
            site_id=seeded_users["site_c_id"],
            user_id=seeded_users["u3_id"],
            content="Tenant B",
            private_flag=False,
        )
        legacy = Note(
            tenant_id=seeded_users["tenant_id"],
            site_id=None,
            user_id=1,
            content="Legacy unscoped",
            private_flag=False,
        )
        db.add_all([note_a, note_b, note_c, legacy])
        db.commit()
        db.refresh(note_a)
        db.refresh(note_b)
        db.refresh(note_c)
        db.refresh(legacy)
        snapshots = {
            "b": (note_b.content, note_b.private_flag, note_b.site_id),
            "c": (note_c.content, note_c.private_flag, note_c.site_id),
        }
        note_b_id = note_b.id
        note_c_id = note_c.id
        legacy_id = legacy.id
    finally:
        db.close()

    login_response = login(client, seeded_users["u1_email"], seeded_users["site_id"])
    assert login_response.status_code == 200
    access_token = login_response.get_json()["access_token"]
    listed = client.get("/notes/").get_json()["notes"]
    listed_ids = {item["id"] for item in listed}
    assert note_a.id in listed_ids
    assert note_b_id not in listed_ids
    assert note_c_id not in listed_ids
    assert legacy_id not in listed_ids

    client.post("/auth/logout")
    stateless_client = app.test_client()
    bearer_a = stateless_client.get(
        f"/notes/?site_id={seeded_users['site_id']}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert bearer_a.status_code == 200
    bearer_b = app.test_client().get(
        f"/notes/?site_id={seeded_users['site_b_id']}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert bearer_b.status_code in (401, 403)
    assert login(client, seeded_users["u1_email"], seeded_users["site_id"]).status_code == 200

    assert client.put(
        f"/notes/{note_b_id}", json={"content": "tampered"}
    ).status_code == 404
    assert client.delete(f"/notes/{note_b_id}").status_code == 404
    assert client.put(
        f"/notes/{note_c_id}", json={"content": "tampered"}
    ).status_code == 404

    db = get_session()
    try:
        assert db.get(Note, note_b_id).content == snapshots["b"][0]
        assert db.get(Note, note_b_id).site_id == snapshots["b"][2]
        assert db.get(Note, note_c_id).content == snapshots["c"][0]
        assert db.get(Note, note_c_id).site_id == snapshots["c"][2]
    finally:
        db.close()

    with client.session_transaction() as sess:
        sess["site_id"] = seeded_users["site_b_id"]
    db = get_session()
    try:
        db.execute(
            text("DELETE FROM kitchen_user_sites WHERE user_id=:user_id"),
            {"user_id": seeded_users["u1_id"]},
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (:user_id, :tenant_id, :site_id)"
            ),
            {
                "user_id": seeded_users["u1_id"],
                "tenant_id": seeded_users["tenant_id"],
                "site_id": seeded_users["site_b_id"],
            },
        )
        db.commit()
    finally:
        db.close()
    client.post("/auth/logout")
    assert login(client, seeded_users["u1_email"], seeded_users["site_b_id"]).status_code == 200
    moved_ids = {item["id"] for item in client.get("/notes/").get_json()["notes"]}
    assert note_a.id not in moved_ids
    assert note_b_id in moved_ids
