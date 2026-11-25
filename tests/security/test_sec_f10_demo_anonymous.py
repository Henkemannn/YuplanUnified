import uuid

import pytest
from sqlalchemy import text

from core.app_factory import create_app
from core.db import create_all, get_session
from core.models import Tenant
from tests._auth_site_helpers import login_bound_user


SECRET_KEY = "isolated-sec-f10-key-0123456789abcdef0123456789"
CUSTOMER_MARKER = "SEC-F10-CUSTOMER-MARKER"
DEPARTMENT_MARKER = "SEC-F10-DEPARTMENT-MARKER"


def _isolated_demo_app(tmp_path, monkeypatch, *, testing=True, env=None, **overrides):
    database_url = f"sqlite:///{(tmp_path / 'sec-f10-demo.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(tmp_path / "builder.db"))
    monkeypatch.setenv("SECRET_KEY", SECRET_KEY)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DEMO_UI", "1")
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    monkeypatch.delenv("STAGING_SIMPLE_AUTH", raising=False)
    if env:
        if any(name in env for name in ("DEPLOY_ENV", "FLASK_ENV")):
            monkeypatch.delenv("APP_ENV", raising=False)
            monkeypatch.delenv("FLASK_ENV", raising=False)
        for name, value in env.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)

    config = {
        "TESTING": testing,
        "SECRET_KEY": SECRET_KEY,
        "JWT_SECRET": "isolated-sec-f10-jwt-0123456789abcdef0123456789",
        "database_url": database_url,
        "BUILDER_DB_PATH": str(tmp_path / "builder.db"),
    }
    config.update(overrides)
    app = create_app(config)
    with app.app_context():
        create_all()
    return app


def _enable_demo_data_features(app):
    registry = app.feature_registry
    for name in ("ff.admin.enabled", "ff.planera.enabled", "ff.report.enabled"):
        if not registry.has(name):
            registry.add(name)
        registry.set(name, True)


def _seed_demo_scope(app):
    site_ids = {
        "a1": f"sec-f10-a1-{uuid.uuid4().hex}",
        "a2": f"sec-f10-a2-{uuid.uuid4().hex}",
        "b1": f"sec-f10-b1-{uuid.uuid4().hex}",
    }
    department_ids = {
        "a1": f"sec-f10-dept-a1-{uuid.uuid4().hex}",
        "a2": f"sec-f10-dept-a2-{uuid.uuid4().hex}",
        "b1": f"sec-f10-dept-b1-{uuid.uuid4().hex}",
    }

    with app.app_context():
        db = get_session()
        try:
            db.add_all(
                [
                    Tenant(id=1, name=f"SEC-F10 Tenant A {uuid.uuid4().hex}"),
                    Tenant(id=2, name=f"SEC-F10 Tenant B {uuid.uuid4().hex}"),
                ]
            )
            db.flush()
            for key, tenant_id, site_name in (
                ("a1", 1, f"{CUSTOMER_MARKER} A1"),
                ("a2", 1, f"{CUSTOMER_MARKER} A2"),
                ("b1", 2, f"{CUSTOMER_MARKER} B1"),
            ):
                db.execute(
                    text(
                        "INSERT INTO sites(id, tenant_id, name, version) "
                        "VALUES(:site_id, :tenant_id, :name, 0)"
                    ),
                    {
                        "site_id": site_ids[key],
                        "tenant_id": tenant_id,
                        "name": site_name,
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO departments("
                        "id, site_id, name, resident_count_mode, resident_count_fixed, version"
                        ") VALUES(:department_id, :site_id, :name, 'fixed', 7, 0)"
                    ),
                    {
                        "department_id": department_ids[key],
                        "site_id": site_ids[key],
                        "name": f"{DEPARTMENT_MARKER} {key.upper()}",
                    },
                )
            db.commit()
        finally:
            db.close()
    return site_ids, department_ids


def _assert_no_customer_markers(response):
    body = response.get_data(as_text=True)
    assert CUSTOMER_MARKER not in body
    assert DEPARTMENT_MARKER not in body


def test_local_demo_shell_and_health_response_are_data_free(tmp_path, monkeypatch):
    app = _isolated_demo_app(tmp_path, monkeypatch)
    _seed_demo_scope(app)
    client = app.test_client()

    demo = client.get("/demo")
    assert demo.status_code == 200
    _assert_no_customer_markers(demo)

    demo_head = client.head("/demo")
    assert demo_head.status_code == 200
    _assert_no_customer_markers(demo_head)

    ping = client.get("/demo/ping")
    assert ping.status_code == 200
    assert ping.get_json() == {"ok": "true"}
    _assert_no_customer_markers(ping)

    ui_demo = client.get("/ui/demo")
    assert ui_demo.status_code == 200
    _assert_no_customer_markers(ui_demo)


def test_anonymous_demo_api_calls_cannot_read_synthetic_tenant_data(
    tmp_path, monkeypatch
):
    app = _isolated_demo_app(tmp_path, monkeypatch)
    _enable_demo_data_features(app)
    site_ids, department_ids = _seed_demo_scope(app)
    client = app.test_client()
    query = {
        "site": site_ids["a1"],
        "site_id": site_ids["a1"],
        "department_id": department_ids["a1"],
        "year": 2026,
        "week": 1,
        "format": "csv",
    }
    protected_routes = (
        "/admin/sites",
        "/admin/departments",
        "/admin/alt2",
        "/admin/menu-choice",
        "/menu-choice",
        "/api/planera/day",
        "/api/planera/week",
        "/api/planera/week/csv",
        "/api/report",
        "/api/report/export",
    )

    route_rules = {
        route: [rule for rule in app.url_map.iter_rules() if rule.rule == route]
        for route in protected_routes
    }
    for route, rules in route_rules.items():
        assert rules, f"protected route is not registered: {route}"
        assert any("GET" in rule.methods for rule in rules), (
            f"protected route does not support GET: {route}",
            [sorted(rule.methods) for rule in rules],
        )
        assert any("HEAD" in rule.methods for rule in rules), (
            f"protected route does not support HEAD: {route}",
            [sorted(rule.methods) for rule in rules],
        )

    statuses = {}
    for route in protected_routes:
        statuses[route] = {}
        for method in ("get", "head"):
            response = getattr(client, method)(route, query_string=query)
            statuses[route][method.upper()] = response.status_code
            assert response.status_code in (401, 403), (
                route,
                method,
                response.status_code,
                response.get_data(as_text=True),
            )
            _assert_no_customer_markers(response)
    print(f"SEC-F10 protected anonymous statuses: {statuses}")


def test_local_placeholder_login_does_not_authorize_real_tenant_data(
    tmp_path, monkeypatch
):
    app = _isolated_demo_app(
        tmp_path,
        monkeypatch,
        testing=False,
        env={"STAGING_SIMPLE_AUTH": "1"},
        DEMO_AUTH_ENABLED=True,
    )
    _enable_demo_data_features(app)
    site_ids, department_ids = _seed_demo_scope(app)
    client = app.test_client()

    login = client.post("/auth/login", json={"role": "admin"})
    assert login.status_code == 200
    assert login.get_json() == {"ok": True, "demo": True, "role": "admin"}

    query = {
        "site": site_ids["a1"],
        "site_id": site_ids["a1"],
        "department_id": department_ids["a1"],
        "year": 2026,
        "week": 1,
    }
    for route in (
        "/admin/sites",
        "/admin/departments",
        "/admin/alt2",
        "/admin/menu-choice",
        "/menu-choice",
        "/api/planera/week",
        "/api/report",
    ):
        response = client.get(route, query_string=query)
        assert response.status_code in (401, 403), (
            route,
            response.status_code,
            response.get_data(as_text=True),
        )
        _assert_no_customer_markers(response)


@pytest.mark.parametrize(
    "environment",
    (
        {"DEPLOY_ENV": "staging"},
        {"DEPLOY_ENV": "pilot"},
        {"DEPLOY_ENV": "production"},
        {"FLY_APP_NAME": "sec-f10-staging"},
    ),
)
def test_demo_and_bypass_routes_are_disabled_outside_local(
    tmp_path, monkeypatch, environment
):
    app = _isolated_demo_app(
        tmp_path,
        monkeypatch,
        testing=False,
        env={"STAGING_SIMPLE_AUTH": "1", **environment},
        DEMO_AUTH_ENABLED=True,
    )
    client = app.test_client()

    assert client.get("/demo").status_code == 404
    assert client.head("/demo").status_code == 404
    assert client.get("/demo/ping").status_code == 404
    assert client.get("/ui/demo").status_code == 404
    assert client.get("/_routes").status_code == 404

    login = client.post("/auth/login", json={"role": "admin"})
    assert login.status_code in (400, 401)
    assert login.get_json().get("demo") is None


def test_local_route_diagnostic_is_separate_from_tenant_data_and_legacy_demo_is_unregistered(
    tmp_path, monkeypatch
):
    app = _isolated_demo_app(tmp_path, monkeypatch)
    _enable_demo_data_features(app)
    _seed_demo_scope(app)
    client = app.test_client()

    routes = client.get("/_routes", headers={"X-Demo-Debug": "1"})
    assert routes.status_code == 200
    route_list = routes.get_json()["routes"]
    assert "GET /demo" in route_list
    assert "GET /demo/ping" in route_list
    assert all("SEC-F10" not in route for route in route_list)
    assert all(rule.endpoint != "demo.index" for rule in app.url_map.iter_rules())

    anonymous_routes = client.get("/_routes")
    assert anonymous_routes.status_code == 403
    _assert_no_customer_markers(anonymous_routes)


def test_bound_user_can_read_own_site_but_not_other_sites_or_tenants(
    tmp_path, monkeypatch
):
    app = _isolated_demo_app(tmp_path, monkeypatch)
    _enable_demo_data_features(app)
    site_ids, _ = _seed_demo_scope(app)
    client = app.test_client()
    login_bound_user(client, site_id=site_ids["a1"])

    own = client.get("/admin/departments", query_string={"site": site_ids["a1"]})
    assert own.status_code == 200
    assert DEPARTMENT_MARKER + " A1" in own.get_data(as_text=True)

    for foreign_site, foreign_marker in (
        (site_ids["a2"], DEPARTMENT_MARKER + " A2"),
        (site_ids["b1"], DEPARTMENT_MARKER + " B1"),
    ):
        foreign = client.get(
            "/admin/departments", query_string={"site": foreign_site}
        )
        assert foreign.status_code == 403
        assert foreign_marker not in foreign.get_data(as_text=True)
        _assert_no_customer_markers(foreign)

    anonymous = app.test_client()
    anonymous_response = anonymous.get(
        "/admin/departments", query_string={"site": site_ids["a1"]}
    )
    assert anonymous_response.status_code == 401
    _assert_no_customer_markers(anonymous_response)
