from __future__ import annotations

from datetime import date
import os
import secrets

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash

from tests.migrations.test_residents_schedule_migration import _upgrade
from tests.migrations.test_users_updated_at_migration import (
    _assert_postgresql_database,
    _validate_postgresql_url,
    _without_libpq_destination_environment,
)


def test_postgresql_authenticated_scope_and_cohort(tmp_path, monkeypatch):
    admin_url = os.environ.get("SEC_PG_07_TEST_DATABASE_URL")
    runtime_url = os.environ.get("SEC_PG_07_RUNTIME_DATABASE_URL")
    runtime_password = os.environ.get("SEC_PG_07_RUNTIME_PASSWORD")
    if not all((admin_url, runtime_url, runtime_password)):
        pytest.skip("Explicit isolated PostgreSQL admin and runtime URLs and runtime password required")

    admin = _validate_postgresql_url(admin_url)
    runtime = _validate_postgresql_url(runtime_url)
    assert (admin.host, admin.port, admin.database) == (runtime.host, runtime.port, runtime.database)
    assert runtime.username and runtime.username != admin.username
    assert not admin.password and not runtime.password
    assert runtime.username.startswith("secpg")
    own = "11111111-1111-4111-8111-111111111111"
    same = "22222222-2222-4222-8222-222222222222"
    other = "33333333-3333-4333-8333-333333333333"
    password = secrets.token_urlsafe(24)
    with _without_libpq_destination_environment():
        _assert_postgresql_database(admin_url, require_empty=True)
        _upgrade(monkeypatch, admin_url, "head")
        admin_engine = create_engine(admin_url)
        quoted_role = admin_engine.dialect.identifier_preparer.quote(runtime.username)
        with admin_engine.begin() as conn:
            role = conn.execute(text(
                "SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=:name"
            ), {"name": runtime.username}).one()
            assert role == (False, False, False)
            conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {quoted_role}"))
            conn.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {quoted_role}"))
            conn.execute(text(
                "GRANT INSERT, UPDATE, DELETE ON weekview_registrations, weekview_versions, "
                "weekview_residents_count, weekview_alt2_flags, department_requirement_group_completions, "
                "department_residents_schedule, department_residents_weekly, meal_registrations, "
                "auth_login_throttles, auth_login_throttle_reservations, department_menu_choices "
                f"TO {quoted_role}"
            ))
            conn.execute(text(f"GRANT INSERT ON pilot_activity_events TO {quoted_role}"))
            conn.execute(text(f"GRANT UPDATE ON users TO {quoted_role}"))
            conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}"))
            conn.execute(text(
                "INSERT INTO tenants(id,name) VALUES (7101,'Synthetic tenant'),(7102,'Other tenant')"
            ))
            conn.execute(text(
                "INSERT INTO sites(id,name,tenant_id) VALUES "
                "('a1','Synthetic site',7101),('a2','Other site',7101),('b1','Foreign site',7102)"
            ))
            for dep, site in ((own, "a1"), (same, "a1"), (other, "a2")):
                conn.execute(text(
                    "INSERT INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed) "
                    "VALUES (:id,:site,:name,'fixed',5)"
                ), {"id": dep, "site": site, "name": f"Synthetic department {dep[0]}"})
            for group, dep in (("g1", own), ("g2", same)):
                conn.execute(text(
                    "INSERT INTO department_requirement_groups(id,department_id,label,default_quantity,is_active) "
                    "VALUES (:id,:dep,'Synthetic group',1,true)"
                ), {"id": group, "dep": dep})
            conn.execute(text(
                "INSERT INTO users(id,tenant_id,email,username,password_hash,role,department_id) "
                "VALUES (7101,7101,'admin@example.test','admin',:password,'admin',:dep)"
            ), {"password": generate_password_hash(password), "dep": own})
            conn.execute(text(
                "INSERT INTO users(id,tenant_id,email,username,password_hash,role,department_id) "
                "VALUES (7102,7101,'portal@example.test','portal',:password,'unit_portal',:dep)"
            ), {"password": generate_password_hash(password), "dep": own})
            conn.execute(text(
                "INSERT INTO dietary_types(tenant_id,site_id,name,requirement_key,semantics,default_select) "
                "VALUES (7101,'a1','Synthetic own','synthetic-own','atomic',true),"
                "(7101,'a2','Synthetic other','synthetic-other','atomic',true)"
            ))

        monkeypatch.setenv("PGPASSWORD", runtime_password)
        monkeypatch.setenv("DATABASE_URL", runtime_url)
        monkeypatch.setenv("BUILDER_DB_PATH", str(tmp_path / "builder.db"))
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("STAGING_SIMPLE_AUTH", "0")
        monkeypatch.setenv("DEMO_AUTH_ENABLED", "0")
        monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
        monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_SECRET", secrets.token_urlsafe(48))
        monkeypatch.delenv("DEV_DEPARTMENT_ID", raising=False)
        from core.app_factory import create_app
        from core.admin_repo import DietTypesRepo, SitesRepo
        import core.db as db_module
        from core.weekview.cohort_bulk_completion_service import (
            CohortBulkCompletionTarget,
            WeekviewCohortBulkCompletionService,
        )
        from core.weekview.cohort_completion_service import WeekviewCohortCompletionService

        app = create_app({"TESTING": False, "SECRET_KEY": secrets.token_hex(32)})
        if not app.feature_registry.has("ff.weekview.enabled"):
            app.feature_registry.add("ff.weekview.enabled")
        app.feature_registry.set("ff.weekview.enabled", True)
        engine = db_module._engine
        with engine.connect() as conn:
            assert conn.dialect.name == "postgresql"
            identity = conn.execute(text(
                "SELECT current_user,current_database(),host(inet_server_addr()),inet_server_port(),"
                "current_schema(),has_schema_privilege(current_user,'public','CREATE'),"
                "(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname='public' "
                "AND c.relkind IN ('r','p') AND r.rolname=current_user)"
            )).one()
            assert identity == (runtime.username, runtime.database, runtime.host, runtime.port, "public", False, 0)
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", capture)
        try:
            client = app.test_client()
            assert client.post("/auth/login", json={"email": "admin@example.test", "password": password}).status_code == 200
            assert [item["name"] for item in DietTypesRepo().list_all(site_id="a1")] == ["Synthetic own"]
            assert {item["id"] for item in SitesRepo().list_sites_for_tenant(7101)} == {"a1", "a2"}
            query = {"year": 2026, "week": 15, "department_id": own}
            response = client.get("/api/weekview", query_string=query)
            assert response.status_code == 200
            etag = response.headers["ETag"]
            denied = client.get(
                "/api/weekview", query_string={**query, "department_id": other},
                headers={"If-None-Match": etag},
            )
            assert denied.status_code == 403 and "ETag" not in denied.headers
            csrf = client.get_cookie("csrf_token").value
            body = {
                "site_id": "a2", "department_id": other, "year": 2026, "week": 15,
                "date": "2026-04-06", "meal_type": "lunch", "registered": "1",
                "csrf_token": csrf,
            }
            assert client.post("/ui/weekview/registration", data=body).status_code == 403
            assert client.post("/ui/weekview/registration", data={**body, "site_id": "a1", "department_id": own}).status_code == 302
            portal_client = app.test_client()
            assert portal_client.post("/auth/login", json={"email": "portal@example.test", "password": password}).status_code == 200
            portal_csrf = portal_client.get_cookie("csrf_token").value
            assert portal_client.post("/ui/weekview/registration", data={
                **body, "site_id": "a1", "department_id": same, "csrf_token": portal_csrf,
            }).status_code == 403
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT tenant_id,site_id,department_id,registered FROM meal_registrations"
                )).all() == [(7101, "a1", own, 1)]
            single = WeekviewCohortCompletionService().set_marked_with_weekview_version(
                tenant_id=7101, department_id=own, year=2026, week=19,
                expected_base_version=0, group_id="g1", service_date="2026-05-04",
                meal="lunch", marked=True,
            )
            assert single["ok"] and single["new_version"] == 1
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT marked FROM department_requirement_group_completions WHERE group_id='g1'"
                )).scalar_one() is True
            targets = [
                CohortBulkCompletionTarget(own, "g1", date(2026, 5, 11), "lunch"),
                CohortBulkCompletionTarget(same, "g2", date(2026, 5, 11), "lunch"),
            ]
            bulk = WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=7101, year=2026, week=20, expected_base_versions={own: 0, same: 0},
                targets=targets, marked=True,
            )
            assert bulk["target_count"] == 2 and bulk["marked"] is True
            assert not [s for s in statements if s.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))]
        finally:
            event.remove(engine, "before_cursor_execute", capture)
            engine.dispose()
            admin_engine.dispose()
