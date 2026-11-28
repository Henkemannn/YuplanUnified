from __future__ import annotations

import re
import secrets

import pytest
from sqlalchemy import event, text
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session, init_engine
from core.models import Base, Department, DietaryType, Site, Tenant, User
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
        db.add_all([
            DietaryType(id=101, tenant_id=1, site_id="a1", name="Gluten-free"),
            DietaryType(id=102, tenant_id=1, site_id="a2", name="Dairy-free"),
            DietaryType(id=103, tenant_id=2, site_id="b1", name="Nut-free"),
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
        db.add(User(
            id=6, tenant_id=1, email="super@example.test", username="super",
            password_hash=generate_password_hash(password), role="superuser", is_active=True,
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
    app.feature_registry.add("ff.planera.enabled")
    app.feature_registry.set("ff.planera.enabled", True)
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


def test_authenticated_diet_writes_enforce_site_scope_and_atomicity(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    login = client.post("/auth/login", json={"email": "admin@example.test", "password": password})
    assert login.status_code == 200
    page = client.get(
        "/ui/kitchen/planering",
        query_string={"site_id": "a1", "year": 2026, "week": 15},
    )
    assert page.status_code == 200
    csrf_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', page.get_data(as_text=True))
    assert csrf_match is not None
    csrf_token = csrf_match.group(1)
    headers = {"X-CSRF-Token": csrf_token}
    query = {"year": 2026, "week": 15, "department_id": OWN, "site_id": "a1"}
    initial = client.get("/api/weekview", query_string=query)
    assert initial.status_code == 200
    etag = initial.headers["ETag"]

    def snapshot():
        db = get_session()
        try:
            registrations = db.execute(text(
                "SELECT tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked "
                "FROM weekview_registrations WHERE department_id=:dep ORDER BY diet_type"
            ), {"dep": OWN}).all()
            version = db.execute(text(
                "SELECT version FROM weekview_versions "
                "WHERE tenant_id=1 AND department_id=:dep AND year=2026 AND week=15"
            ), {"dep": OWN}).scalar_one()
            return registrations, version
        finally:
            db.close()

    def mark(diet_type_id, marked, match, **extra):
        body = {
            "department_id": OWN,
            "site_id": "a1",
            "local_date": "2026-04-06",
            "meal": "lunch",
            "diet_type_id": str(diet_type_id),
            "marked": marked,
            **extra,
        }
        return client.patch(
            "/api/weekview/specialdiets/mark",
            json=body,
            headers={**headers, "If-Match": match},
        )

    saved = mark(101, True, etag)
    assert saved.status_code == 200
    saved_state = snapshot()
    assert saved_state[0][0][-2:] == ("101", True)

    stale = mark(101, False, etag)
    assert stale.status_code == 412
    assert snapshot() == saved_state

    cleared = mark(101, False, saved.headers["ETag"])
    assert cleared.status_code == 200
    cleared_state = snapshot()
    assert cleared_state[0][0][-2:] == ("101", False)
    assert cleared_state[1] > saved_state[1]

    latest_etag = cleared.headers["ETag"]
    for diet_id, status_code in ((102, 403), (103, 403), (999, 400), ("veg", 400)):
        before = snapshot()
        denied = mark(diet_id, True, latest_etag)
        assert denied.status_code == status_code
        assert snapshot() == before

    for extra, status_code in (({"site_id": "a2"}, 403), ({"tenant_id": 2}, 400)):
        before = snapshot()
        denied = mark(101, True, latest_etag, **extra)
        assert denied.status_code == status_code
        assert snapshot() == before

    before = snapshot()
    bulk = client.patch(
        "/api/weekview",
        json={
            "tenant_id": 1,
            "site_id": "a1",
            "department_id": OWN,
            "year": 2026,
            "week": 15,
            "operations": [
                {"day_of_week": 1, "meal": "lunch", "diet_type": "101", "marked": True},
                {"day_of_week": 1, "meal": "lunch", "diet_type": "102", "marked": True},
            ],
        },
        headers={**headers, "If-Match": latest_etag},
    )
    assert bulk.status_code == 403
    assert snapshot() == before

    before_bulk = snapshot()
    for path in ("/api/planering/mark_produced_special", "/api/planering/clear_produced_special"):
        denied_bulk = client.post(
            path,
            json={
                "site_id": "a1",
                "year": 2026,
                "week": 15,
                "day_index": 0,
                "meal": "lunch",
                "diet_type_ids": ["102"],
            },
            headers=headers,
        )
        assert denied_bulk.status_code == 403, denied_bulk.get_json()
        assert snapshot() == before_bulk

    exclusion_payload = {
        "site_id": "a1",
        "year": 2026,
        "week": 15,
        "day_index": 0,
        "meal": "lunch",
        "alt": "1",
        "diet_type_id": "101",
    }
    exclusion = client.post(
        "/api/kitchen/planering/normal_exclusions/toggle",
        json=exclusion_payload,
        headers=headers,
    )
    assert exclusion.status_code == 200
    assert exclusion.get_json()["excluded"] is True
    for diet_id, status_code in (("102", 403), ("103", 403), ("999", 400), ("veg", 400)):
        db = get_session()
        try:
            before_exclusions = db.execute(text(
                "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                "FROM normal_exclusions ORDER BY site_id,diet_type_id"
            )).all()
        finally:
            db.close()
        denied = client.post(
            "/api/kitchen/planering/normal_exclusions/toggle",
            json={**exclusion_payload, "diet_type_id": diet_id},
            headers=headers,
        )
        assert denied.status_code == status_code
        db = get_session()
        try:
            assert db.execute(text(
                "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                "FROM normal_exclusions ORDER BY site_id,diet_type_id"
            )).all() == before_exclusions
        finally:
            db.close()


@pytest.mark.parametrize("department", [OTHER_SITE, OTHER_TENANT, UNKNOWN])
def test_legacy_weekview_denies_out_of_scope_departments(authenticated_app, department):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    db = get_session()
    try:
        before = db.execute(text("SELECT count(*) FROM weekview_versions")).scalar_one()
    finally:
        db.close()
    response = client.get("/ui/weekview", query_string={
        "site_id": "a1", "department_id": department, "year": 2026, "week": 15,
    })
    assert response.status_code == 403
    assert "ETag" not in response.headers
    assert "Other site" not in response.get_data(as_text=True)
    assert "Other tenant" not in response.get_data(as_text=True)
    db = get_session()
    try:
        assert db.execute(text("SELECT count(*) FROM weekview_versions")).scalar_one() == before
    finally:
        db.close()


def test_legacy_weekview_department_bound_user_cannot_read_other_department(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "portal@example.test", "password": password}).status_code == 200
    query = {"site_id": "a1", "year": 2026, "week": 15}
    denied = client.get("/ui/weekview", query_string={**query, "department_id": SAME_SITE})
    assert denied.status_code == 403
    assert "Same" not in denied.get_data(as_text=True)
    own = client.get("/ui/weekview", query_string={**query, "department_id": OWN})
    assert own.status_code == 200
    assert "Own" in own.get_data(as_text=True)
    no_department = client.get("/ui/weekview", query_string=query)
    assert no_department.status_code == 200
    assert "Own" in no_department.get_data(as_text=True)
    assert "Same" not in no_department.get_data(as_text=True)
    db = get_session()
    try:
        assert db.execute(text(
            "SELECT count(*) FROM weekview_versions WHERE department_id=:dep"
        ), {"dep": SAME_SITE}).scalar_one() == 0
    finally:
        db.close()


def test_legacy_weekview_uses_bound_site_for_admin(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    query = {"site_id": "a2", "year": 2026, "week": 15}
    for department, name in ((OWN, "Own"), (SAME_SITE, "Same")):
        response = client.get("/ui/weekview", query_string={**query, "department_id": department})
        assert response.status_code == 200
        assert name in response.get_data(as_text=True)
        assert "Other site" not in response.get_data(as_text=True)
    overview = client.get("/ui/weekview", query_string=query)
    assert overview.status_code == 200
    assert "Own" in overview.get_data(as_text=True)
    assert "Other site" not in overview.get_data(as_text=True)


def test_legacy_weekview_preserves_superuser_scope(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "super@example.test", "password": password}).status_code == 200
    query = {"site_id": "a2", "year": 2026, "week": 15}
    allowed = client.get("/ui/weekview", query_string={**query, "department_id": OTHER_SITE})
    assert allowed.status_code == 200
    assert "Other site" in allowed.get_data(as_text=True)
    assert client.get("/ui/weekview", query_string=query).status_code == 200
    assert client.get("/ui/weekview", query_string={**query, "site_id": "b1"}).status_code == 403


@pytest.mark.parametrize("site", ["", "a2"])
def test_legacy_weekview_rejects_missing_or_invalid_binding(authenticated_app, site):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    with client.session_transaction() as session:
        session["site_id"] = site
    response = client.get("/ui/weekview", query_string={
        "site_id": "a1", "department_id": OWN, "year": 2026, "week": 15,
    })
    assert response.status_code in (401, 403)
    assert "Own" not in response.get_data(as_text=True)


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


@pytest.mark.parametrize("table", [
    "department_diet_defaults", "department_diet_overrides", "dietary_types",
])
def test_missing_diet_schema_fails_closed_before_conditional_get(authenticated_app, table):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    query = {"year": 2026, "week": 15, "department_id": OWN}
    response = client.get("/api/weekview", query_string=query)
    assert response.status_code == 200
    etag = response.headers["ETag"]
    db = get_session()
    try:
        db.execute(text(f"DROP TABLE {table}"))
        db.commit()
    finally:
        db.close()
    assert client.get("/api/weekview", query_string=query).status_code == 500
    assert client.get("/ui/weekview", query_string={**query, "site_id": "a1"}).status_code == 500
    response = client.get("/api/weekview", query_string=query, headers={"If-None-Match": etag})
    assert response.status_code == 500
    assert "ETag" not in response.headers


@pytest.mark.parametrize("corruption", ["semantics", "count", "count_type", "column_type"])
def test_invalid_diet_data_fails_closed_before_conditional_get(authenticated_app, corruption):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    query = {"year": 2026, "week": 15, "department_id": OWN}
    response = client.get("/api/weekview", query_string=query)
    assert response.status_code == 200
    etag = response.headers["ETag"]
    db = get_session()
    try:
        if corruption == "semantics":
            db.execute(text(
                "INSERT INTO dietary_types(tenant_id, site_id, name, semantics, default_select) "
                "VALUES (1, 'a1', 'Synthetic', 'invalid', 0)"
            ))
        elif corruption == "column_type":
            db.execute(text("DROP TABLE department_diet_defaults"))
            db.execute(text(
                "CREATE TABLE department_diet_defaults "
                "(department_id TEXT, diet_type_id TEXT, default_count TEXT)"
            ))
        else:
            db.execute(text(
                "INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count) "
                "VALUES (:department, 'synthetic', :count)"
            ), {"department": OWN, "count": -1 if corruption == "count" else "invalid"})
        db.commit()
    finally:
        db.close()
    db = get_session()
    try:
        versions_before = db.execute(text("SELECT count(*) FROM weekview_versions")).scalar_one()
    finally:
        db.close()
    for headers in ({}, {"If-None-Match": etag}):
        response = client.get("/api/weekview", query_string=query, headers=headers)
        assert response.status_code == 500
        assert "ETag" not in response.headers
    db = get_session()
    try:
        assert db.execute(text("SELECT count(*) FROM weekview_versions")).scalar_one() == versions_before
    finally:
        db.close()


def test_invalid_diet_semantics_in_other_site_does_not_block_own_site(authenticated_app):
    app, password = authenticated_app
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    db = get_session()
    try:
        db.execute(text(
            "INSERT INTO dietary_types(tenant_id, site_id, name, semantics, default_select) "
            "VALUES (1, 'a2', 'Other site synthetic', 'invalid', 0)"
        ))
        db.commit()
    finally:
        db.close()
    response = client.get("/api/weekview", query_string={"year": 2026, "week": 15, "department_id": OWN})
    assert response.status_code == 200


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


def test_authenticated_builder_runtime_never_provisions_or_repairs(authenticated_app, monkeypatch):
    import sqlite3
    from core.builder_sqlite import initialize_builder_sqlite

    app, password = authenticated_app
    builder_path = app.config["BUILDER_DB_PATH"]
    initialize_builder_sqlite(builder_path)
    with sqlite3.connect(builder_path) as conn:
        before = list(conn.iterdump())

    statements = []
    original_connect = sqlite3.connect

    def capture(*args, **kwargs):
        conn = original_connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(sqlite3, "connect", capture)
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    assert client.get("/api/builder/menus").status_code == 200
    with original_connect(builder_path) as conn:
        assert list(conn.iterdump()) == before
    csrf = client.get_cookie("csrf_token").value
    response = client.post(
        "/api/builder/components", json={"component_name": "Synthetic component"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201
    component_id = response.get_json()["component"]["component_id"]
    assert client.get("/api/builder/components").status_code == 200
    assert client.patch(
        f"/api/builder/components/{component_id}", json={"category": "sauce"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 200
    assert client.delete(
        f"/api/builder/components/{component_id}", headers={"X-CSRF-Token": csrf},
    ).status_code == 200
    imported = client.post(
        "/api/builder/import/sessions",
        json={
            "source_name": "Synthetic import", "import_type": "component_list",
            "items": [{"selected": True, "item_type": "component", "raw_text": "Synthetic potato",
                       "name": "Synthetic potato", "components": []}],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert imported.status_code == 201
    session_id = imported.get_json()["session"]["session_id"]
    published = client.post(
        f"/api/builder/import/sessions/{session_id}/publish-selected",
        json={}, headers={"X-CSRF-Token": csrf},
    )
    assert published.status_code == 200
    assert published.get_json()["summary"]["imported_count"] == 1
    assert any(
        item["component_name"] == "Synthetic potato"
        for item in client.get("/api/builder/library").get_json()["components"]
    )
    ddl = [s for s in statements if s.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))]
    assert not ddl, ddl
    print(f"BUILDER_AUTHENTICATED_DDL_COUNT={len(ddl)}")

    with original_connect(builder_path) as conn:
        conn.execute("DROP TABLE builder_menus")
    statements.clear()
    response = client.get("/api/builder/menus")
    assert response.status_code == 500
    assert not [s for s in statements if s.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/builder/components/private", {"component_name": "Synthetic private component"}),
        ("/api/builder/compositions/private", {"composition_name": "Synthetic private dish"}),
    ],
)
def test_private_builder_creation_fails_closed_without_actor(authenticated_app, monkeypatch, tmp_path, path, payload):
    import sqlite3
    import core.builder_api as builder_api
    from core.builder_sqlite import initialize_builder_sqlite

    app, password = authenticated_app
    builder_path = app.config["BUILDER_DB_PATH"]
    initialize_builder_sqlite(builder_path)
    with sqlite3.connect(builder_path) as conn:
        before = list(conn.iterdump())
    client = app.test_client()
    assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
    csrf = client.get_cookie("csrf_token").value
    with sqlite3.connect(tmp_path / "auth.db") as conn:
        main_before = list(conn.iterdump())
    monkeypatch.setattr(builder_api, "_get_builder_actor", lambda: None)
    response = client.post(path, json=payload, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 401
    assert response.get_json() == {"ok": False, "error": "unauthorized", "message": "authentication required"}
    with sqlite3.connect(builder_path) as conn:
        assert list(conn.iterdump()) == before
    with sqlite3.connect(tmp_path / "auth.db") as conn:
        assert list(conn.iterdump()) == main_before
