from __future__ import annotations

from datetime import date
import os
import re
import secrets
import sqlite3
from types import SimpleNamespace

import pytest
from flask import template_rendered
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
                "auth_login_throttles, auth_login_throttle_reservations, department_menu_choices, "
                "dietary_types, department_diet_defaults, normal_exclusions "
                f"TO {quoted_role}"
            ))
            conn.execute(text(f"GRANT INSERT ON pilot_activity_events TO {quoted_role}"))
            conn.execute(text(f"GRANT UPDATE ON users, departments TO {quoted_role}"))
            conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}"))
            conn.execute(text(
                "INSERT INTO tenants(id,name) VALUES (7101,'Synthetic tenant'),(7102,'Other tenant')"
            ))
            conn.execute(text(
                "INSERT INTO sites(id,name,tenant_id) VALUES "
                "('a1','Synthetic site',7101),('a2','Other site',7101),('b1','Foreign site',7102),"
                "(:planera_site,'Planera synthetic site',7101),"
                "(:planera_other_site,'Planera other site',7101),"
                "(:planera_foreign_site,'Planera foreign site',7102)"
            ), {
                "planera_site": "44444444-4444-4444-8444-444444444444",
                "planera_other_site": "55555555-5555-4555-8555-555555555555",
                "planera_foreign_site": "66666666-6666-4666-8666-666666666666",
            })
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
                "INSERT INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed) "
                "VALUES ('77777777-7777-4777-8777-777777777777', "
                "'44444444-4444-4444-8444-444444444444', 'Planera department', 'fixed', 10)"
            ))
            conn.execute(text(
                "INSERT INTO users(id,tenant_id,email,username,password_hash,role,department_id) "
                "VALUES (7101,7101,'admin@example.test','admin',:password,'admin',:dep)"
            ), {"password": generate_password_hash(password), "dep": own})
            conn.execute(text(
                "INSERT INTO users(id,tenant_id,email,username,password_hash,role,department_id) "
                "VALUES (7102,7101,'portal@example.test','portal',:password,'unit_portal',:dep)"
            ), {"password": generate_password_hash(password), "dep": own})
            conn.execute(text(
                "INSERT INTO users(id,tenant_id,email,username,password_hash,role,department_id) "
                "VALUES (7103,7101,'planera@example.test','planera',:password,'admin',"
                "'77777777-7777-4777-8777-777777777777')"
            ), {"password": generate_password_hash(password)})
            conn.execute(text(
                "INSERT INTO dietary_types(tenant_id,site_id,name,requirement_key,semantics,default_select) "
                "VALUES (7101,'a1','Synthetic own','synthetic-own','atomic',true),"
                "(7101,'a2','Synthetic other','synthetic-other','atomic',true),"
                "(7102,'b1','Synthetic foreign','synthetic-foreign','atomic',true)"
            ))

        monkeypatch.setenv("PGPASSWORD", runtime_password)
        monkeypatch.setenv("DATABASE_URL", runtime_url)
        monkeypatch.setenv("BUILDER_DB_PATH", str(tmp_path / "builder.db"))
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("YUPLAN_STRICT_CSRF", "1")
        monkeypatch.setenv("DEV_CSRF_LAX", "0")
        monkeypatch.setenv("STAGING_SIMPLE_AUTH", "0")
        monkeypatch.setenv("DEMO_AUTH_ENABLED", "0")
        monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
        monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_SECRET", secrets.token_urlsafe(48))
        monkeypatch.delenv("DEV_DEPARTMENT_ID", raising=False)
        from core.builder_sqlite import initialize_builder_sqlite
        initialize_builder_sqlite(tmp_path / "builder.db")
        builder_statements = []
        original_connect = sqlite3.connect

        def capture_builder(path, *args, **kwargs):
            conn = original_connect(path, *args, **kwargs)
            conn.set_trace_callback(builder_statements.append)
            return conn

        monkeypatch.setattr(sqlite3, "connect", capture_builder)
        from core.app_factory import create_app
        from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
        import core.db as db_module
        from core.planera_product2_page3_vm import Product2Page3CompletionTargetVM
        from core.weekview.cohort_bulk_completion_service import (
            CohortBulkCompletionTarget,
            WeekviewCohortBulkCompletionService,
        )
        from core.weekview.cohort_completion_service import WeekviewCohortCompletionService
        from core.weekview.service import WeekviewService

        app = create_app({"TESTING": False, "SECRET_KEY": secrets.token_hex(32)})
        if not app.feature_registry.has("ff.weekview.enabled"):
            app.feature_registry.add("ff.weekview.enabled")
        app.feature_registry.set("ff.weekview.enabled", True)
        if not app.feature_registry.has("ff.planera.enabled"):
            app.feature_registry.add("ff.planera.enabled")
        app.feature_registry.set("ff.planera.enabled", True)
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
            assert {item["id"] for item in SitesRepo().list_sites_for_tenant(7101)} == {
                "a1",
                "a2",
                "44444444-4444-4444-8444-444444444444",
                "55555555-5555-4555-8555-555555555555",
            }
            csrf = client.get_cookie("csrf_token").value
            created = client.post(
                "/ui/admin/specialkost/new",
                data={"name": "Synthetic created", "diet_family": "Allergi / Exkludering",
                      "default_select": "1", "csrf_token": csrf},
            )
            assert created.status_code == 302 and created.location.endswith("/ui/admin/specialkost")
            planera_site = "44444444-4444-4444-8444-444444444444"
            planera_department = "77777777-7777-4777-8777-777777777777"
            planera_diet_id = DietTypesRepo().create(
                site_id=planera_site,
                name="Synthetic Planera diet",
                default_select=True,
                semantics="atomic",
            )
            with engine.connect() as conn:
                planera_department_version = conn.execute(
                    text("SELECT version FROM departments WHERE id=:department_id"),
                    {"department_id": planera_department},
                ).scalar_one()
            DepartmentsRepo().upsert_department_diet_defaults(
                planera_department,
                planera_department_version,
                [{"diet_type_id": planera_diet_id, "default_count": 2}],
            )
            planera_client = app.test_client()
            assert planera_client.post(
                "/auth/login",
                json={"email": "planera@example.test", "password": password},
            ).status_code == 200
            planera_read = planera_client.get(
                "/api/planera/day",
                query_string={
                    "site_id": planera_site,
                    "date": "2026-04-06",
                    "department_id": planera_department,
                },
            )
            assert planera_read.status_code == 200, planera_read.get_json()
            planera_department_payload = next(
                item
                for item in planera_read.get_json()["departments"]
                if item["department_id"] == planera_department
            )
            planera_lunch = planera_department_payload["meals"]["lunch"]
            planera_diet = next(
                item
                for item in planera_lunch["special_diets"]
                if item["diet_type_id"] == str(planera_diet_id)
            )
            assert planera_lunch["residents_total"] == 10
            assert planera_lunch["normal_diet_count"] == 8
            assert planera_diet["count"] == 2
            for denied_site in (
                "55555555-5555-4555-8555-555555555555",
                "66666666-6666-4666-8666-666666666666",
            ):
                denied_planera_read = planera_client.get(
                    "/api/planera/day",
                    query_string={
                        "site_id": denied_site,
                        "date": "2026-04-06",
                    },
                )
                assert denied_planera_read.status_code == 404

            with admin_engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO department_requirement_groups"
                    "(id,department_id,label,default_quantity,is_active) "
                    "VALUES ('g-planera',:department_id,'Planera production group',1,true)"
                ), {"department_id": own})
            planera_service_date = date(2026, 6, 8)
            planera_year, planera_week, _ = planera_service_date.isocalendar()
            planera_target = Product2Page3CompletionTargetVM(
                requirement_group_id="g-planera",
                destination_id=own,
                service_date=planera_service_date.isoformat(),
                meal="lunch",
                quantity=1,
            )
            monkeypatch.setattr(
                "core.planera_api.build_product2_page3_vm",
                lambda **_: SimpleNamespace(
                    ready=True,
                    blockers=(),
                    completion_targets=(planera_target,),
                    target_variant_type="main",
                ),
            )
            planera_weekview = WeekviewService()
            planera_base_version = planera_weekview.get_effective_version(
                7101, planera_year, planera_week, own, "a1"
            )
            planera_etag = planera_weekview.build_etag(
                7101, own, planera_year, planera_week, planera_base_version
            )
            csrf = client.get_cookie("csrf_token").value
            completion_payload = {
                "site_id": "a1",
                "service_date": planera_service_date.isoformat(),
                "meal": "lunch",
                "marked": True,
                "expected_etags": {own: planera_etag},
            }
            completion = client.post(
                "/api/planera/product2/production-completion",
                json=completion_payload,
                headers={"X-CSRF-Token": csrf},
            )
            assert completion.status_code == 200, completion.get_json()
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT marked FROM department_requirement_group_completions "
                    "WHERE group_id='g-planera' AND service_date=:service_date AND meal_key='lunch'"
                ), {"service_date": planera_service_date.isoformat()}).scalar_one() is True
                completion_version = conn.execute(text(
                    "SELECT version FROM weekview_versions "
                    "WHERE tenant_id=7101 AND department_id=:dep AND year=:year AND week=:week"
                ), {
                    "dep": own,
                    "year": planera_year,
                    "week": planera_week,
                }).scalar_one()
                assert completion_version == 1
            stale_completion = client.post(
                "/api/planera/product2/production-completion",
                json=completion_payload,
                headers={"X-CSRF-Token": csrf},
            )
            assert stale_completion.status_code == 412
            clear_completion_payload = {
                **completion_payload,
                "marked": False,
                "expected_etags": {
                    own: completion.get_json()["department_etags"][own]
                },
            }
            cleared_completion = client.post(
                "/api/planera/product2/production-completion",
                json=clear_completion_payload,
                headers={"X-CSRF-Token": csrf},
            )
            assert cleared_completion.status_code == 200
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT marked FROM department_requirement_group_completions "
                    "WHERE group_id='g-planera' AND service_date=:service_date AND meal_key='lunch'"
                ), {"service_date": planera_service_date.isoformat()}).scalar_one() is False
            with engine.connect() as conn:
                diet_id = conn.execute(text(
                    "SELECT id FROM dietary_types WHERE tenant_id=7101 AND site_id='a1' "
                    "AND name='Synthetic created' AND default_select=true"
                )).scalar_one()
                version = conn.execute(text(
                    "SELECT version FROM departments WHERE id=:dep"
                ), {"dep": own}).scalar_one()
            if not app.feature_registry.has("ff.admin.enabled"):
                app.feature_registry.add("ff.admin.enabled")
            app.feature_registry.set("ff.admin.enabled", True)
            page = client.get(
                "/ui/kitchen/planering", query_string={"site_id": "a1", "year": 2026, "week": 15}
            )
            assert page.status_code == 200
            token = re.search(r'<meta name="csrf-token" content="([^"]+)"', page.get_data(as_text=True))
            assert token is not None
            default_headers = {
                "X-CSRF-Token": token.group(1),
                "If-Match": f'W/"admin:dept:{own}:v{version}"',
            }
            default_body = {"items": [{"diet_type_id": str(diet_id), "default_count": 2}]}
            saved = client.put(
                f"/admin/departments/{own}/diet-defaults", json=default_body, headers=default_headers
            )
            assert saved.status_code == 200, (saved.status_code, saved.get_json())
            assert saved.get_json()["items"][0]["default_count"] == 2
            stale = client.put(
                f"/admin/departments/{own}/diet-defaults",
                json={"items": [{"diet_type_id": str(diet_id), "default_count": 9}]},
                headers=default_headers,
            )
            assert stale.status_code == 412
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT diet_type_id,default_count FROM department_diet_defaults WHERE department_id=:dep"
                ), {"dep": own}).all() == [(diet_id, 2)]
                other_diet = conn.execute(text(
                    "SELECT id FROM dietary_types WHERE tenant_id=7101 AND site_id='a2'"
                )).scalar_one()
                before_version = conn.execute(text(
                    "SELECT version FROM departments WHERE id=:dep"
                ), {"dep": own}).scalar_one()
            invalid = client.put(
                f"/admin/departments/{own}/diet-defaults",
                json={"items": [{"diet_type_id": str(other_diet), "default_count": 8}]},
                headers={"X-CSRF-Token": token.group(1), "If-Match": saved.headers["ETag"]},
            )
            assert invalid.status_code == 400
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT diet_type_id,default_count FROM department_diet_defaults WHERE department_id=:dep"
                ), {"dep": own}).all() == [(diet_id, 2)]
                assert conn.execute(text(
                    "SELECT version FROM departments WHERE id=:dep"
                ), {"dep": own}).scalar_one() == before_version
            query = {"year": 2026, "week": 15, "department_id": own}
            response = client.get("/api/weekview", query_string=query)
            assert response.status_code == 200
            diets = response.get_json()["department_summaries"][0]["days"][0]["diets"]["lunch"]
            created_diet = next(row for row in diets if row["diet_type_id"] == str(diet_id))
            assert created_diet["resident_count"] == 2 and created_diet["marked"] is True
            rendered = []

            def capture_template(_sender, template, context, **_extra):
                if template.name == "ui/kitchen_planering_v1.html":
                    rendered.append(context["vm"])

            template_rendered.connect(capture_template, app, weak=False)
            try:
                production = client.get(
                    "/ui/kitchen/planering",
                    query_string={
                        "site_id": "a1", "year": 2026, "week": 15,
                        "day": 0, "meal": "lunch", "selected_diets": str(diet_id),
                    },
                )
            finally:
                template_rendered.disconnect(capture_template, app)
            assert production.status_code == 200 and len(rendered) == 1
            assert rendered[0]["diet_counts_by_dept"][own][str(diet_id)] == 2
            assert rendered[0]["summary"]["special_to_adapt_total"] == 2
            assert any(
                item["diet_type_id"] == str(diet_id)
                and item["diet_type_name"] == "Synthetic created"
                and item["total_count"] == 2
                for item in rendered[0]["diet_options"]
            )
            etag = response.headers["ETag"]
            invalid_identity_id = None
            try:
                with admin_engine.begin() as conn:
                    invalid_identity_id = conn.execute(
                        text(
                            "INSERT INTO dietary_types"
                            "(tenant_id,site_id,name,diet_family,requirement_key,semantics,default_select) "
                            "VALUES (7101,'a1',:name,'Other',:requirement_key,'invalid',false) "
                            "RETURNING id"
                        ),
                        {
                            "name": f"Synthetic invalid identity {secrets.token_hex(6)}",
                            "requirement_key": f"invalid_{secrets.token_hex(6)}",
                        },
                    ).scalar_one()
                with engine.connect() as conn:
                    versions_before = conn.execute(
                        text("SELECT count(*) FROM weekview_versions")
                    ).scalar_one()
                for headers in ({}, {"If-None-Match": etag}):
                    invalid_identity_response = client.get(
                        "/api/weekview",
                        query_string=query,
                        headers=headers,
                    )
                    assert invalid_identity_response.status_code == 500
                    assert "ETag" not in invalid_identity_response.headers
                with engine.connect() as conn:
                    assert conn.execute(
                        text("SELECT count(*) FROM weekview_versions")
                    ).scalar_one() == versions_before
            finally:
                if invalid_identity_id is not None:
                    with admin_engine.begin() as conn:
                        conn.execute(
                            text("DELETE FROM dietary_types WHERE id=:id"),
                            {"id": invalid_identity_id},
                        )
            write_headers = {"X-CSRF-Token": token.group(1)}
            exclusion_payload = {
                "site_id": "a1",
                "year": 2026,
                "week": 15,
                "day_index": 0,
                "meal": "lunch",
                "alt": "1",
                "diet_type_id": str(diet_id),
            }
            excluded = client.post(
                "/api/kitchen/planering/normal_exclusions/toggle",
                json=exclusion_payload,
                headers=write_headers,
            )
            assert excluded.status_code == 200, excluded.get_json()
            assert excluded.get_json()["excluded"] is True
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                    "FROM normal_exclusions"
                )).all() == [(7101, "a1", 2026, 15, 0, "lunch", "1", diet_id)]
            unexcluded = client.post(
                "/api/kitchen/planering/normal_exclusions/toggle",
                json=exclusion_payload,
                headers=write_headers,
            )
            assert unexcluded.status_code == 200 and unexcluded.get_json()["excluded"] is False
            with engine.connect() as conn:
                assert conn.execute(text("SELECT count(*) FROM normal_exclusions")).scalar_one() == 0

            def mark(diet_id, marked, match, **extra):
                return client.patch(
                    "/api/weekview/specialdiets/mark",
                    json={
                        "site_id": "a1", "department_id": own, "local_date": "2026-04-06",
                        "meal": "lunch", "diet_type_id": str(diet_id), "marked": marked, **extra,
                    },
                    headers={**write_headers, "If-Match": match},
                )

            def mark_snapshot():
                with engine.connect() as conn:
                    rows = conn.execute(text(
                        "SELECT tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked "
                        "FROM weekview_registrations WHERE department_id=:dep AND year=2026 AND week=15 "
                        "ORDER BY diet_type"
                    ), {"dep": own}).all()
                    version = conn.execute(text(
                        "SELECT version FROM weekview_versions "
                        "WHERE tenant_id=7101 AND department_id=:dep AND year=2026 AND week=15"
                    ), {"dep": own}).scalar_one_or_none()
                    return rows, version

            marked = mark(diet_id, True, etag)
            assert marked.status_code == 200, marked.get_json()
            marked_state = mark_snapshot()
            assert marked_state[0][0][-2:] == (str(diet_id), True)
            stale_mark = mark(diet_id, False, etag)
            assert stale_mark.status_code == 412
            assert mark_snapshot() == marked_state
            cleared = mark(diet_id, False, marked.headers["ETag"])
            assert cleared.status_code == 200, cleared.get_json()
            cleared_state = mark_snapshot()
            assert cleared_state[0][0][-2:] == (str(diet_id), False)
            assert cleared_state[1] > marked_state[1]
            latest_etag = cleared.headers["ETag"]
            foreign_diet = None
            with engine.connect() as conn:
                foreign_diet = conn.execute(text(
                    "SELECT id FROM dietary_types WHERE tenant_id=7102 AND site_id='b1'"
                )).scalar_one()
            for denied_id, expected_status in (
                (other_diet, 403), (foreign_diet, 403), (999999, 400), ("veg", 400),
            ):
                before = mark_snapshot()
                denied_mark = mark(denied_id, True, latest_etag)
                assert denied_mark.status_code == expected_status, denied_mark.get_json()
                assert mark_snapshot() == before
            for extra, expected_status in (({"site_id": "a2"}, 403), ({"tenant_id": 7102}, 400)):
                before = mark_snapshot()
                denied_mark = mark(diet_id, True, latest_etag, **extra)
                assert denied_mark.status_code == expected_status, denied_mark.get_json()
                assert mark_snapshot() == before
            before_bulk = mark_snapshot()
            mixed_bulk = client.patch(
                "/api/weekview",
                json={
                    "tenant_id": 7101, "site_id": "a1", "department_id": own,
                    "year": 2026, "week": 15,
                    "operations": [
                        {"day_of_week": 1, "meal": "lunch", "diet_type": str(diet_id), "marked": True},
                        {"day_of_week": 1, "meal": "lunch", "diet_type": str(other_diet), "marked": True},
                    ],
                },
                headers={**write_headers, "If-Match": latest_etag},
            )
            assert mixed_bulk.status_code == 403
            assert mark_snapshot() == before_bulk
            for path, body in (
                (
                    "/api/planering/mark_produced_special",
                    {
                        "site_id": "a1", "year": 2026, "week": 15, "day_index": 0,
                        "meal": "lunch", "diet_type_ids": [str(other_diet)],
                    },
                ),
                (
                    "/api/planering/clear_produced_special",
                    {
                        "site_id": "a1", "year": 2026, "week": 15, "day_index": 0,
                        "meal": "lunch", "diet_type_ids": [str(other_diet)],
                    },
                ),
                (
                    "/api/kitchen/planering/normal_exclusions/toggle",
                    {
                        "site_id": "a1", "year": 2026, "week": 15, "day_index": 0,
                        "meal": "lunch", "alt": "1", "diet_type_id": str(other_diet),
                    },
                ),
            ):
                denied = client.post(path, json=body, headers=write_headers)
                assert denied.status_code == 403, (path, denied.get_json())
                assert mark_snapshot() == before_bulk
            etag = latest_etag
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
            ui_query = {"site_id": "a1", "year": 2026, "week": 21}
            assert client.get("/ui/weekview", query_string={**ui_query, "department_id": own}).status_code == 200
            assert client.get("/ui/weekview", query_string={**ui_query, "department_id": other}).status_code == 403
            assert portal_client.get("/ui/weekview", query_string={**ui_query, "department_id": same}).status_code == 403
            assert portal_client.get("/ui/weekview", query_string=ui_query).status_code == 200
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT count(*) FROM weekview_versions "
                    "WHERE department_id=:dep AND year=2026 AND week=21"
                ), {"dep": same}).scalar_one() == 0
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
            assert client.get("/api/builder/menus").status_code == 200
            assert not [s for s in statements if s.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))]
            assert builder_statements
            assert not [s for s in builder_statements if s.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))]
        finally:
            event.remove(engine, "before_cursor_execute", capture)
            engine.dispose()
            admin_engine.dispose()
