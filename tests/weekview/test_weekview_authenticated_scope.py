from __future__ import annotations

import secrets

import pytest
from sqlalchemy import event, text
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session, init_engine
from core.models import Base, Department, Site, Tenant, User
from core.weekview.schema import ensure_weekview_schema


OWN = "11111111-1111-4111-8111-111111111111"
SAME_SITE = "22222222-2222-4222-8222-222222222222"
OTHER_SITE = "33333333-3333-4333-8333-333333333333"
OTHER_TENANT = "44444444-4444-4444-8444-444444444444"
UNKNOWN = "55555555-5555-4555-8555-555555555555"


@pytest.fixture
def authenticated_app(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'auth.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(tmp_path / "builder.db"))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("STAGING_SIMPLE_AUTH", "0")
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_SECRET", secrets.token_urlsafe(48))
    monkeypatch.delenv("DEV_DEPARTMENT_ID", raising=False)
    engine = init_engine(url, force=True)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        ensure_weekview_schema(conn)
    password = secrets.token_urlsafe(24)
    db = get_session()
    try:
        db.add_all([Tenant(id=1, name="Synthetic A", active=True), Tenant(id=2, name="Synthetic B", active=True)])
        db.add_all([
            Site(id="a1", name="A1", tenant_id=1),
            Site(id="a2", name="A2", tenant_id=1),
            Site(id="b1", name="B1", tenant_id=2),
        ])
        db.add_all([
            Department(id=OWN, site_id="a1", name="Own"),
            Department(id=SAME_SITE, site_id="a1", name="Same"),
            Department(id=OTHER_SITE, site_id="a2", name="Other site"),
            Department(id=OTHER_TENANT, site_id="b1", name="Other tenant"),
        ])
        for index, role in enumerate(("viewer", "editor", "admin"), start=1):
            db.add(User(
                id=index, tenant_id=1, email=f"{role}@example.test",
                username=role, password_hash=generate_password_hash(password),
                role=role, department_id=OWN, is_active=True,
            ))
        db.add(User(
            id=4, tenant_id=1, email="unbound@example.test", username="unbound",
            password_hash=generate_password_hash(password), role="editor",
            department_id=None, is_active=True,
        ))
        db.add(User(
            id=5, tenant_id=1, email="portal@example.test", username="portal",
            password_hash=generate_password_hash(password), role="unit_portal",
            department_id=OWN, is_active=True,
        ))
        db.commit()
        db.execute(text(
            "INSERT INTO weekview_registrations "
            "(tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked) "
            "VALUES (1, :dep, 2026, 15, 1, 'lunch', 'private-marker', 1)"
        ), {"dep": OTHER_SITE})
        db.commit()
    finally:
        db.close()
    app = create_app({"TESTING": False, "SECRET_KEY": secrets.token_hex(32)})
    assert app.config["TESTING"] is False
    app.feature_registry.add("ff.weekview.enabled")
    app.feature_registry.set("ff.weekview.enabled", True)
    return app, password


@pytest.mark.parametrize("role", ["viewer", "editor", "admin"])
def test_authenticated_scope_precedes_get_and_etag(authenticated_app, role):
    app, password = authenticated_app
    client = app.test_client()
    login = client.post("/auth/login", json={"email": f"{role}@example.test", "password": password})
    assert login.status_code == 200
    query = {"year": 2026, "week": 15, "department_id": OWN}
    response = client.get("/api/weekview", query_string=query)
    assert response.status_code == 200
    etag = response.headers["ETag"]
    assert client.get("/api/weekview", query_string=query, headers={"If-None-Match": etag}).status_code == 304
    assert client.get("/api/weekview", query_string={**query, "department_id": SAME_SITE}).status_code == 200
    for denied in (OTHER_SITE, OTHER_TENANT, UNKNOWN):
        response = client.get(
            "/api/weekview",
            query_string={**query, "department_id": denied, "site_id": "a2", "tenant_id": 2},
            headers={"If-None-Match": etag},
        )
        assert response.status_code == 403
        assert "ETag" not in response.headers
        assert "private-marker" not in response.get_data(as_text=True)
    db = get_session()
    try:
        assert db.execute(text(
            "SELECT count(*) FROM weekview_versions WHERE department_id IN (:a, :b, :c)"
        ), {"a": OTHER_SITE, "b": OTHER_TENANT, "c": UNKNOWN}).scalar_one() == 0
    finally:
        db.close()
    assert client.get("/api/weekview", query_string={"year": 2026, "week": 15}).status_code == 200
    own_with_manipulated_queries = client.get(
        "/api/weekview", query_string={**query, "site_id": "a2", "tenant_id": 2}
    )
    assert own_with_manipulated_queries.status_code == 200
    assert "private-marker" not in own_with_manipulated_queries.get_data(as_text=True)
    assert client.get("/api/weekview/resolve", query_string={
        "site": "a2", "department_id": OTHER_SITE, "date": "2026-04-06"
    }).status_code == 403
    if role == "admin":
        for path in ("/ui/kitchen/week", "/ui/portal/week"):
            forbidden = client.get(path, query_string={
                "site_id": "a2", "department_id": OTHER_SITE, "year": 2026, "week": 15
            })
            assert forbidden.status_code == 403
            assert "Other site" not in forbidden.get_data(as_text=True)


def test_missing_site_binding_rejected(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    response = client.post("/auth/login", json={"email": "unbound@example.test", "password": password})
    assert response.status_code == 403


def test_invalid_site_binding_rejected(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "editor@example.test", "password": password}).status_code == 200
    with client.session_transaction() as session:
        session["site_id"] = "a2"
    response = client.get("/api/weekview", query_string={"year": 2026, "week": 15, "department_id": OTHER_SITE})
    assert response.status_code in (401, 403)
    assert "ETag" not in response.headers


def test_conditional_get_fails_closed_when_residents_schema_is_missing(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "editor@example.test", "password": password}).status_code == 200
    query = {"year": 2026, "week": 15, "department_id": OWN}
    response = client.get("/api/weekview", query_string=query)
    assert response.status_code == 200
    etag = response.headers["ETag"]
    db = get_session()
    try:
        db.execute(text("DROP TABLE department_residents_schedule"))
        db.commit()
    finally:
        db.close()
    response = client.get("/api/weekview", query_string=query, headers={"If-None-Match": etag})
    assert response.status_code == 500
    assert response.status_code != 304
    assert "ETag" not in response.headers


@pytest.mark.parametrize("site,department", [("a2", OTHER_SITE), ("b1", OTHER_TENANT)])
def test_registration_rejects_cross_scope_body(authenticated_app, site, department):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    csrf = client.get_cookie("csrf_token").value
    response = client.post("/ui/weekview/registration", data={
        "site_id": site, "department_id": department, "year": "2026", "week": "15",
        "date": "2026-04-06", "meal_type": "lunch", "registered": "1",
        "csrf_token": csrf,
    })
    assert response.status_code == 403
    db = get_session()
    try:
        assert db.execute(text("SELECT count(*) FROM meal_registrations")).scalar_one() == 0
    finally:
        db.close()


def test_registration_accepts_own_scope_and_persists(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    csrf = client.get_cookie("csrf_token").value
    response = client.post("/ui/weekview/registration", data={
        "site_id": "a1", "department_id": OWN, "year": "2026", "week": "15",
        "date": "2026-04-06", "meal_type": "lunch", "registered": "1",
        "csrf_token": csrf,
    })
    assert response.status_code == 302
    db = get_session()
    try:
        assert db.execute(text(
            "SELECT tenant_id,site_id,department_id,registered FROM meal_registrations"
        )).one() == (1, "a1", OWN, 1)
    finally:
        db.close()


def test_portal_registration_cannot_target_another_department(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "portal@example.test", "password": password}).status_code == 200
    csrf = client.get_cookie("csrf_token").value
    body = {
        "site_id": "a1", "department_id": SAME_SITE, "year": "2026", "week": "15",
        "date": "2026-04-06", "meal_type": "lunch", "registered": "1", "csrf_token": csrf,
    }
    assert client.post("/ui/weekview/registration", data=body).status_code == 403
    db = get_session()
    try:
        assert db.execute(text("SELECT count(*) FROM meal_registrations")).scalar_one() == 0
    finally:
        db.close()
    assert client.post("/ui/weekview/registration", data={**body, "department_id": OWN}).status_code == 302


def test_authenticated_weekview_runtime_does_not_issue_ddl(authenticated_app):
    app, password = authenticated_app
    import core.db as db_module

    statements = []
    engine = db_module._engine

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        client = app.test_client()
        assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
        query = {"site_id": "a1", "department_id": OWN, "year": 2026, "week": 15}
        assert client.get("/api/weekview", query_string=query).status_code == 200
        assert client.get("/ui/portal/week", query_string=query).status_code == 200
        assert client.get("/ui/kitchen/week", query_string=query).status_code == 200
        ddl = [s for s in statements if s.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))]
        assert not ddl, "\n".join(sorted({s.strip().splitlines()[0] for s in ddl}))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
