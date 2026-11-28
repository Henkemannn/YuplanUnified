from __future__ import annotations

import csv
import io
import json
import os
import secrets
import uuid

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash


YEAR = 2026
WEEK = 17
_ENV_KEYS = (
    "SEC_FINAL_07F_MIGRATOR_URL",
    "SEC_FINAL_07F_RUNTIME_URL",
    "SEC_FINAL_07F_MIGRATOR_PASSWORD",
    "SEC_FINAL_07F_RUNTIME_PASSWORD",
)


def _validated_url(value: str, expected_user: str):
    url = make_url(value)
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "127.0.0.1"
    assert url.port is not None
    assert url.database and url.database.startswith("sec_final_07f_")
    assert url.username == expected_user
    assert url.password is None
    assert not url.query
    return url


def _department_rows_xlsx(body: bytes) -> list[tuple[object, ...]]:
    workbook = load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    try:
        return list(workbook["departments"].iter_rows(min_row=2, values_only=True))
    finally:
        workbook.close()


def test_authenticated_report_and_department_settings_postgresql(
    tmp_path, monkeypatch
):
    values = {key: os.environ.get(key) for key in _ENV_KEYS}
    if not all(values.values()):
        pytest.skip(
            "Explicit isolated SEC-FINAL-07F PostgreSQL migrator/runtime "
            "URLs and credentials required"
        )

    migrator_url = _validated_url(values[_ENV_KEYS[0]], "sec07f_migrator")
    runtime_url = _validated_url(values[_ENV_KEYS[1]], "sec07f_runtime")
    assert (
        migrator_url.host,
        migrator_url.port,
        migrator_url.database,
    ) == (
        runtime_url.host,
        runtime_url.port,
        runtime_url.database,
    )
    assert migrator_url.username != runtime_url.username

    for key in (
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSSLMODE",
    ):
        monkeypatch.delenv(key, raising=False)

    admin_engine = create_engine(
        migrator_url.set(password=values[_ENV_KEYS[2]]), future=True
    )
    runtime_engine = create_engine(
        runtime_url.set(password=values[_ENV_KEYS[3]]), future=True
    )
    try:
        with runtime_engine.connect() as conn:
            identity = conn.execute(
                text(
                    "SELECT current_user, current_database(), "
                    "host(inet_server_addr()), inet_server_port(), current_schema(), "
                    "has_schema_privilege(current_user, 'public', 'CREATE'), "
                    "(SELECT pg_get_userbyid(datdba) FROM pg_database "
                    "WHERE datname=current_database())"
                )
            ).one()
            assert identity == (
                "sec07f_runtime",
                runtime_url.database,
                "127.0.0.1",
                runtime_url.port,
                "public",
                False,
                "sec07f_migrator",
            )
            role = conn.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole "
                    "FROM pg_roles WHERE rolname=current_user"
                )
            ).one()
            assert role == (False, False, False)
            revision = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert revision == "0059_normal_exclusions_scope"
            columns = conn.execute(
                text(
                    "SELECT table_name, column_name, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema='public' AND "
                    "((table_name='weekview_registrations' AND "
                    "column_name IN ('tenant_id', 'diet_type')) OR "
                    "(table_name='department_diet_defaults' AND "
                    "column_name='diet_type_id'))"
                )
            ).all()
            assert set(columns) == {
                ("weekview_registrations", "tenant_id", "integer"),
                ("weekview_registrations", "diet_type", "text"),
                ("department_diet_defaults", "diet_type_id", "integer"),
            }
        print("POSTGRESQL_RUNTIME_IDENTITY", identity)
        print("POSTGRESQL_MIGRATION_HEAD", revision)
        print("POSTGRESQL_SCHEMA_TYPES", sorted(columns))

        run_id = uuid.uuid4().hex[:8]
        tenant_a_name = f"SEC-FINAL-07F tenant A {run_id}"
        tenant_b_name = f"SEC-FINAL-07F tenant B {uuid.uuid4()}"
        site_ids = {key: str(uuid.uuid4()) for key in ("a1", "a2", "b1")}
        department_ids = {key: str(uuid.uuid4()) for key in site_ids}
        diet_names = {
            "a1": f"SEC-FINAL-07F Gluten A1 {uuid.uuid4().hex[:8]}",
            "a2": f"SEC-FINAL-07F Lactose A2 {uuid.uuid4().hex[:8]}",
            "b1": f"SEC-FINAL-07F Peanut B1 {uuid.uuid4().hex[:8]}",
        }
        user_emails = {
            key: f"sec-final-07f-{key}-{uuid.uuid4().hex[:8]}@example.test"
            for key in ("a1", "a2")
        }
        password = secrets.token_urlsafe(24)
        password_hash = generate_password_hash(password)

        with admin_engine.begin() as conn:
            tenant_a_id = conn.execute(
                text("INSERT INTO tenants(name, active) VALUES(:name, TRUE) RETURNING id"),
                {"name": tenant_a_name},
            ).scalar_one()
            tenant_b_id = conn.execute(
                text("INSERT INTO tenants(name, active) VALUES(:name, TRUE) RETURNING id"),
                {"name": tenant_b_name},
            ).scalar_one()
            diet_ids = {}
            for key, site_id in site_ids.items():
                tenant_id = tenant_b_id if key == "b1" else tenant_a_id
                conn.execute(
                    text(
                        "INSERT INTO sites(id, tenant_id, name, version) "
                        "VALUES(:id, :tenant_id, :name, 0)"
                    ),
                    {
                        "id": site_id,
                        "tenant_id": tenant_id,
                        "name": f"SEC-FINAL-07F site {run_id} {key}",
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO departments("
                        "id, site_id, name, resident_count_mode, "
                        "resident_count_fixed, notes, version"
                        ") VALUES(:id, :site, :name, 'fixed', :count, '', 0)"
                    ),
                    {
                        "id": department_ids[key],
                        "site": site_id,
                        "name": f"SEC-FINAL-07F department {run_id} {key}",
                        "count": {"a1": 10, "a2": 20, "b1": 30}[key],
                    },
                )
                diet_ids[key] = conn.execute(
                    text(
                        "INSERT INTO dietary_types("
                        "tenant_id, site_id, name, diet_family, requirement_key, "
                        "semantics, default_select"
                        ") VALUES(:tenant_id, :site, :name, "
                        "'Allergi / Exkludering', :requirement_key, 'atomic', TRUE) "
                        "RETURNING id"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "site": site_id,
                        "name": diet_names[key],
                        "requirement_key": f"sec07f-{key}-{uuid.uuid4().hex[:8]}",
                    },
                ).scalar_one()
                conn.execute(
                    text(
                        "INSERT INTO department_diet_defaults("
                        "department_id, diet_type_id, default_count"
                        ") VALUES(:department_id, :diet_id, :count)"
                    ),
                    {
                        "department_id": department_ids[key],
                        "diet_id": diet_ids[key],
                        "count": {"a1": 1, "a2": 1, "b1": 2}[key],
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO weekview_versions("
                        "tenant_id, department_id, year, week, version"
                        ") VALUES(:tenant_id, :department_id, :year, :week, 4)"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "department_id": department_ids[key],
                        "year": YEAR,
                        "week": WEEK,
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO weekview_residents_count("
                        "tenant_id, department_id, year, week, day_of_week, meal, count"
                        ") VALUES(:tenant_id, :department_id, :year, :week, 1, 'lunch', :count)"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "department_id": department_ids[key],
                        "year": YEAR,
                        "week": WEEK,
                        "count": {"a1": 10, "a2": 20, "b1": 30}[key],
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO weekview_registrations("
                        "tenant_id, department_id, year, week, day_of_week, meal, "
                        "diet_type, marked"
                        ") VALUES(:tenant_id, :department_id, :year, :week, 1, "
                        "'lunch', :diet_type, 1)"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "department_id": department_ids[key],
                        "year": YEAR,
                        "week": WEEK,
                        "diet_type": str(diet_ids[key]),
                    },
                )
            conn.execute(
                text(
                    "INSERT INTO weekview_registrations("
                    "tenant_id, department_id, year, week, day_of_week, meal, "
                    "diet_type, marked"
                    ") VALUES(:tenant_id, :department_id, :year, :week, 2, "
                    "'lunch', 'Normalkost', 1)"
                ),
                {
                    "tenant_id": tenant_a_id,
                    "department_id": department_ids["a1"],
                    "year": YEAR,
                    "week": WEEK,
                },
            )
            for key in ("a1", "a2"):
                conn.execute(
                    text(
                        "INSERT INTO users("
                        "tenant_id, username, email, password_hash, role, is_active, "
                        "department_id, auth_version, must_change_password"
                        ") VALUES(:tenant_id, :username, :email, :password_hash, "
                        "'admin', TRUE, :department_id, 1, FALSE)"
                    ),
                    {
                        "tenant_id": tenant_a_id,
                        "username": user_emails[key].split("@", 1)[0],
                        "email": user_emails[key],
                        "password_hash": password_hash,
                        "department_id": department_ids[key],
                    },
                )

        for key in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGSERVICE"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DATABASE_URL", str(runtime_url))
        monkeypatch.setenv("PGPASSWORD", values[_ENV_KEYS[3]])
        monkeypatch.setenv("SECRET_KEY", secrets.token_urlsafe(48))
        monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
        monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_SECRET", secrets.token_urlsafe(48))
        monkeypatch.setenv("YUPLAN_STRICT_CSRF", "1")
        monkeypatch.setenv("DEMO_AUTH_ENABLED", "0")
        monkeypatch.setenv("STAGING_SIMPLE_AUTH", "0")
        monkeypatch.setenv("DEV_CSRF_LAX", "0")
        monkeypatch.setenv("BUILDER_DB_PATH", str(tmp_path / "builder.db"))
        monkeypatch.delenv("DEV_DEPARTMENT_ID", raising=False)

        import core.db as db_module
        from core.app_factory import create_app

        engine = db_module.init_engine(str(runtime_url), force=True)
        captured_sql: list[str] = []

        def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
            captured_sql.append(statement)

        event.listen(engine, "before_cursor_execute", capture_sql)
        try:
            app = create_app(
                {
                    "TESTING": False,
                    "SECRET_KEY": os.environ["SECRET_KEY"],
                    "YUPLAN_STRICT_CSRF": True,
                    "BUILDER_DB_PATH": str(tmp_path / "builder.db"),
                }
            )
            assert app.config["TESTING"] is False
            assert app.config["YUPLAN_STRICT_CSRF"] is True
            if not app.feature_registry.has("ff.report.enabled"):
                app.feature_registry.add("ff.report.enabled")
            app.feature_registry.set("ff.report.enabled", True)

            client_a1 = app.test_client()
            client_a2 = app.test_client()
            for client, key in ((client_a1, "a1"), (client_a2, "a2")):
                login = client.post(
                    "/auth/login",
                    json={"email": user_emails[key], "password": password},
                    base_url="https://localhost",
                )
                assert login.status_code == 200, login.get_data(as_text=True)
                with client.session_transaction(base_url="https://localhost") as sess:
                    assert sess.get("site_id") == site_ids[key]

            report_a1 = client_a1.get(
                f"/api/report?year={YEAR}&week={WEEK}&site_id={site_ids['a2']}"
                f"&tenant_id={tenant_b_id}",
                headers={"X-Site-ID": site_ids["a2"]},
                base_url="https://localhost",
            )
            assert report_a1.status_code == 200, report_a1.get_data(as_text=True)
            payload_a1 = report_a1.get_json()
            assert [row["department_id"] for row in payload_a1["departments"]] == [
                department_ids["a1"]
            ]
            assert payload_a1["departments"][0]["lunch"] == {
                "normal": 9,
                "specials": {diet_names["a1"]: 1},
                "total": 10,
            }
            assert payload_a1["totals"]["lunch"] == {
                "normal": 9,
                "specials": {diet_names["a1"]: 1},
                "total": 10,
            }

            same_site = client_a1.get(
                f"/api/report?year={YEAR}&week={WEEK}",
                headers={"If-None-Match": report_a1.headers["ETag"]},
                base_url="https://localhost",
            )
            assert same_site.status_code == 304
            report_a2 = client_a2.get(
                f"/api/report?year={YEAR}&week={WEEK}",
                headers={"If-None-Match": report_a1.headers["ETag"]},
                base_url="https://localhost",
            )
            assert report_a2.status_code == 200
            assert report_a2.headers["ETag"] != report_a1.headers["ETag"]
            assert [row["department_id"] for row in report_a2.get_json()["departments"]] == [
                department_ids["a2"]
            ]
            assert report_a2.get_json()["totals"]["lunch"] == {
                "normal": 19,
                "specials": {diet_names["a2"]: 1},
                "total": 20,
            }
            department_report = client_a1.get(
                f"/api/report?year={YEAR}&week={WEEK}"
                f"&department_id={department_ids['a1']}",
                base_url="https://localhost",
            )
            assert department_report.status_code == 200
            for foreign_department in (department_ids["a2"], department_ids["b1"]):
                denied = client_a1.get(
                    f"/api/report?year={YEAR}&week={WEEK}"
                    f"&department_id={foreign_department}",
                    headers={"If-None-Match": report_a1.headers["ETag"]},
                    base_url="https://localhost",
                )
                assert denied.status_code == 404

            csv_a1 = client_a1.get(
                f"/api/report/export?year={YEAR}&week={WEEK}&format=csv",
                base_url="https://localhost",
            )
            csv_a2 = client_a2.get(
                f"/api/report/export?year={YEAR}&week={WEEK}&format=csv",
                headers={"If-None-Match": csv_a1.headers["ETag"]},
                base_url="https://localhost",
            )
            assert csv_a1.status_code == csv_a2.status_code == 200
            assert csv_a1.headers["ETag"] != csv_a2.headers["ETag"]
            csv_same_site = client_a1.get(
                f"/api/report/export?year={YEAR}&week={WEEK}&format=csv",
                headers={"If-None-Match": csv_a1.headers["ETag"]},
                base_url="https://localhost",
            )
            assert csv_same_site.status_code == 304
            for foreign_department in (department_ids["a2"], department_ids["b1"]):
                denied_export = client_a1.get(
                    f"/api/report/export?year={YEAR}&week={WEEK}&format=csv"
                    f"&department_id={foreign_department}",
                    headers={"If-None-Match": csv_a1.headers["ETag"]},
                    base_url="https://localhost",
                )
                assert denied_export.status_code == 404
            csv_rows = list(csv.reader(io.StringIO(csv_a1.get_data(as_text=True))))
            a1_rows = [row for row in csv_rows if row and row[0] == department_ids["a1"]]
            assert len(a1_rows) == 2
            assert json.loads(next(row for row in a1_rows if row[2] == "lunch")[5]) == {
                diet_names["a1"]: 1
            }
            assert department_ids["a2"] not in csv_a1.get_data(as_text=True)
            assert department_ids["b1"] not in csv_a1.get_data(as_text=True)
            csv_department = client_a1.get(
                f"/api/report/export?year={YEAR}&week={WEEK}&format=csv"
                f"&department_id={department_ids['a1']}",
                base_url="https://localhost",
            )
            assert csv_department.status_code == 200
            csv_department_rows = list(
                csv.reader(io.StringIO(csv_department.get_data(as_text=True)))
            )
            assert len(
                [
                    row
                    for row in csv_department_rows
                    if row and row[0] == department_ids["a1"]
                ]
            ) == 2
            xlsx_a1 = client_a1.get(
                f"/api/report/export?year={YEAR}&week={WEEK}&format=xlsx",
                base_url="https://localhost",
            )
            assert xlsx_a1.status_code == 200
            xlsx_same_site = client_a1.get(
                f"/api/report/export?year={YEAR}&week={WEEK}&format=xlsx",
                headers={"If-None-Match": xlsx_a1.headers["ETag"]},
                base_url="https://localhost",
            )
            assert xlsx_same_site.status_code == 304
            xlsx_rows = _department_rows_xlsx(xlsx_a1.data)
            a1_xlsx_rows = [
                row for row in xlsx_rows if row[0] == department_ids["a1"]
            ]
            assert len(a1_xlsx_rows) == 2
            assert json.loads(
                next(row for row in a1_xlsx_rows if row[2] == "lunch")[5]
            ) == {diet_names["a1"]: 1}
            assert all(
                row[0] not in (department_ids["a2"], department_ids["b1"])
                for row in xlsx_rows
            )
            xlsx_department = client_a1.get(
                f"/api/report/export?year={YEAR}&week={WEEK}&format=xlsx"
                f"&department_id={department_ids['a1']}",
                base_url="https://localhost",
            )
            assert xlsx_department.status_code == 200
            xlsx_department_rows = _department_rows_xlsx(xlsx_department.data)
            assert len(
                [
                    row
                    for row in xlsx_department_rows
                    if row[0] == department_ids["a1"]
                ]
            ) == 2

            settings_path = (
                f"/ui/admin/departments/{department_ids['a1']}/settings"
            )
            settings = client_a1.get(
                settings_path, base_url="https://localhost"
            )
            assert settings.status_code == 200
            settings_html = settings.get_data(as_text=True)
            assert diet_names["a1"] in settings_html
            assert f'value="{diet_ids["a1"]}"' in settings_html
            with client_a1.session_transaction(
                base_url="https://localhost"
            ) as sess:
                csrf_token = sess.get("CSRF_TOKEN")
            assert csrf_token
            form = {
                "residents_base_count": "10",
                "notes": "SEC-FINAL-07F scoped update",
                "diet_type_id[]": str(diet_ids["a1"]),
                "planned_count[]": "3",
            }
            missing_csrf = client_a1.post(
                settings_path, data=form, base_url="https://localhost"
            )
            assert missing_csrf.status_code == 403
            invalid_csrf = client_a1.post(
                settings_path,
                data=form,
                headers={"X-CSRF-Token": "invalid-sec-final-07f-token"},
                base_url="https://localhost",
            )
            assert invalid_csrf.status_code == 403
            for foreign_department in (department_ids["a2"], department_ids["b1"]):
                foreign_get = client_a1.get(
                    f"/ui/admin/departments/{foreign_department}/settings",
                    base_url="https://localhost",
                )
                assert foreign_get.status_code == 403
                foreign_post = client_a1.post(
                    f"/ui/admin/departments/{foreign_department}/settings",
                    data=form,
                    headers={"X-CSRF-Token": csrf_token},
                    base_url="https://localhost",
                )
                assert foreign_post.status_code == 403
            saved = client_a1.post(
                settings_path,
                data=form,
                headers={"X-CSRF-Token": csrf_token},
                base_url="https://localhost",
            )
            assert saved.status_code == 302

            with admin_engine.connect() as conn:
                counts = {
                    key: conn.execute(
                        text(
                            "SELECT default_count FROM department_diet_defaults "
                            "WHERE department_id=:department_id AND diet_type_id=:diet_id"
                        ),
                        {
                            "department_id": department_ids[key],
                            "diet_id": diet_ids[key],
                        },
                    ).scalar_one()
                    for key in ("a1", "a2", "b1")
                }
                assert counts == {"a1": 3, "a2": 1, "b1": 2}

            legacy_value = f"SEC-FINAL-07F legacy {uuid.uuid4().hex}"
            with admin_engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO weekview_registrations("
                        "tenant_id, department_id, year, week, day_of_week, meal, "
                        "diet_type, marked"
                        ") VALUES(:tenant_id, :department_id, :year, :week, 3, "
                        "'lunch', :diet_type, 1)"
                    ),
                    {
                        "tenant_id": tenant_a_id,
                        "department_id": department_ids["a1"],
                        "year": YEAR,
                        "week": WEEK,
                        "diet_type": legacy_value,
                    },
                )
            invalid_reference = client_a1.get(
                f"/api/report?year={YEAR}&week={WEEK}",
                base_url="https://localhost",
            )
            assert invalid_reference.status_code == 503
            assert "report_schema_unavailable" in invalid_reference.get_data(
                as_text=True
            )
            assert legacy_value not in invalid_reference.get_data(as_text=True)
            with admin_engine.connect() as conn:
                stored = conn.execute(
                    text(
                        "SELECT diet_type, marked FROM weekview_registrations "
                        "WHERE department_id=:department_id AND day_of_week=3"
                    ),
                    {"department_id": department_ids["a1"]},
                ).one()
                assert stored == (legacy_value, 1)
        finally:
            event.remove(engine, "before_cursor_execute", capture_sql)

        print("SQL_CAPTURE_REPORT_ADMIN_POSTGRESQL_BEGIN")
        for statement in captured_sql:
            print(statement)
        print("SQL_CAPTURE_REPORT_ADMIN_POSTGRESQL_END")
        assert not any(
            statement.lstrip().upper().startswith(
                ("CREATE ", "ALTER ", "DROP ", "TRUNCATE ")
            )
            for statement in captured_sql
        )
    finally:
        admin_engine.dispose()
        runtime_engine.dispose()
