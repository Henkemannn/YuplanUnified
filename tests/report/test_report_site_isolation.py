from __future__ import annotations

import csv
import io
import json
import uuid

import pytest
from openpyxl import load_workbook
from sqlalchemy import event, text


YEAR = 2026
WEEK = 17


def _enable_report(client) -> None:
    response = client.post(
        "/features/set",
        json={"name": "ff.report.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert response.status_code == 200


def _seed_report_sites(client) -> dict[str, object]:
    from core.admin_repo import DietTypesRepo
    from core.db import get_session
    from core.models import Tenant
    from core.weekview.schema import ensure_weekview_schema

    app = client.application
    site_ids = {key: str(uuid.uuid4()) for key in ("a1", "a2", "b1")}
    department_ids = {key: str(uuid.uuid4()) for key in site_ids}
    diet_names = {"a1": "Gluten A1", "a2": "Lactose A2", "b1": "Peanut B1"}

    with app.app_context():
        db = get_session()
        try:
            tenant_b = Tenant(name=f"Report Tenant B {uuid.uuid4()}")
            db.add(tenant_b)
            db.flush()
            tenant_b_id = int(tenant_b.id)
            ensure_weekview_schema(db.connection())
            for key, site_id in site_ids.items():
                tenant_id = tenant_b_id if key == "b1" else 1
                db.execute(
                    text(
                        "INSERT INTO sites(id, tenant_id, name, version) "
                        "VALUES(:id, :tenant_id, :name, 0)"
                    ),
                    {"id": site_id, "tenant_id": tenant_id, "name": f"Report Site {key}"},
                )
                db.execute(
                    text(
                        "INSERT INTO departments("
                        "id, site_id, name, resident_count_mode, resident_count_fixed, version"
                        ") VALUES(:id, :site_id, :name, 'fixed', 0, 0)"
                    ),
                    {
                        "id": department_ids[key],
                        "site_id": site_id,
                        "name": f"Report Department {key}",
                    },
                )
            db.commit()
        finally:
            db.close()

    diet_ids = {
        key: DietTypesRepo().create(
            site_id=site_ids[key],
            tenant_id=tenant_b_id if key == "b1" else 1,
            name=diet_names[key],
            semantics="atomic",
        )
        for key in site_ids
    }

    with app.app_context():
        db = get_session()
        try:
            for key in site_ids:
                tenant_id = tenant_b_id if key == "b1" else 1
                count = {"a1": 10, "a2": 20, "b1": 30}[key]
                db.execute(
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
                db.execute(
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
                        "count": count,
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO weekview_registrations("
                        "tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked"
                        ") VALUES(:tenant_id, :department_id, :year, :week, 1, 'lunch', :diet_id, 1)"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "department_id": department_ids[key],
                        "year": YEAR,
                        "week": WEEK,
                        "diet_id": str(diet_ids[key]),
                    },
                )
            db.execute(
                text(
                    "INSERT INTO weekview_registrations("
                    "tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked"
                    ") VALUES(1, :department_id, :year, :week, 2, 'lunch', 'Normalkost', 1)"
                ),
                {"department_id": department_ids["a1"], "year": YEAR, "week": WEEK},
            )
            db.commit()
        finally:
            db.close()

    return {
        "tenant_b_id": tenant_b_id,
        "site_ids": site_ids,
        "department_ids": department_ids,
        "diet_names": diet_names,
        "diet_ids": diet_ids,
    }


def _department_rows_xlsx(body: bytes) -> list[tuple[object, ...]]:
    workbook = load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    try:
        return list(workbook["departments"].iter_rows(min_row=2, values_only=True))
    finally:
        workbook.close()


@pytest.fixture
def report_clients(client_admin):
    from tests._auth_site_helpers import login_bound_user

    _enable_report(client_admin)
    data = _seed_report_sites(client_admin)
    login_bound_user(client_admin, site_id=data["site_ids"]["a1"])
    client_a2 = client_admin.application.test_client()
    client_a2.environ_base = {}
    login_bound_user(client_a2, site_id=data["site_ids"]["a2"])
    data["client_a1"] = client_admin
    data["client_a2"] = client_a2
    return data


def test_report_site_etags_are_not_reused(report_clients):
    client_a1 = report_clients["client_a1"]
    client_a2 = report_clients["client_a2"]

    response_a1 = client_a1.get(f"/api/report?year={YEAR}&week={WEEK}")
    response_a2 = client_a2.get(
        f"/api/report?year={YEAR}&week={WEEK}",
        headers={"If-None-Match": response_a1.headers["ETag"]},
    )
    assert response_a1.status_code == 200
    assert response_a2.status_code == 200
    assert response_a2.headers["ETag"] != response_a1.headers["ETag"]

    export_a1 = client_a1.get(
        f"/api/report/export?year={YEAR}&week={WEEK}&format=csv"
    )
    export_a2 = client_a2.get(
        f"/api/report/export?year={YEAR}&week={WEEK}&format=csv",
        headers={"If-None-Match": export_a1.headers["ETag"]},
    )
    assert export_a1.status_code == 200
    assert export_a2.status_code == 200
    assert export_a2.headers["ETag"] != export_a1.headers["ETag"]


def test_report_exports_include_only_bound_site(report_clients):
    client_a1 = report_clients["client_a1"]
    client_a2 = report_clients["client_a2"]
    department_ids = report_clients["department_ids"]
    diet_names = report_clients["diet_names"]

    for client, expected_department, foreign_department, expected_name in (
        (client_a1, department_ids["a1"], department_ids["a2"], diet_names["a1"]),
        (client_a2, department_ids["a2"], department_ids["a1"], diet_names["a2"]),
    ):
        csv_response = client.get(
            f"/api/report/export?year={YEAR}&week={WEEK}&format=csv"
        )
        assert csv_response.status_code == 200
        rows = list(csv.reader(io.StringIO(csv_response.get_data(as_text=True))))
        department_rows = [row for row in rows if row and row[0] == expected_department]
        assert len(department_rows) == 2
        assert all(not row or row[0] != foreign_department for row in rows)
        lunch_row = next(row for row in department_rows if row[2] == "lunch")
        assert json.loads(lunch_row[5]) == {expected_name: 1}

        xlsx_response = client.get(
            f"/api/report/export?year={YEAR}&week={WEEK}&format=xlsx"
        )
        assert xlsx_response.status_code == 200
        xlsx_rows = _department_rows_xlsx(xlsx_response.data)
        department_rows = [
            row for row in xlsx_rows if row[0] == expected_department
        ]
        assert len(department_rows) == 2
        assert all(row[0] != foreign_department for row in xlsx_rows)
        lunch_row = next(row for row in department_rows if row[2] == "lunch")
        assert json.loads(lunch_row[5]) == {expected_name: 1}


def test_report_reads_do_not_execute_runtime_ddl(report_clients):
    from core.db import get_session

    client = report_clients["client_a1"]
    engine = get_session().get_bind()
    captured_sql: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        captured_sql.append(statement)

    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        response = client.get(f"/api/report?year={YEAR}&week={WEEK}")
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)

    assert response.status_code == 200
    print("SQL_CAPTURE_REPORT_SQLITE_BEGIN")
    for statement in captured_sql:
        print(statement)
    print("SQL_CAPTURE_REPORT_SQLITE_END")
    assert not any(
        statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "TRUNCATE "))
        for statement in captured_sql
    )


@pytest.mark.usefixtures("client_admin")
def test_report_and_exports_are_bound_to_authenticated_site(client_admin):
    from tests._auth_site_helpers import login_bound_user
    from core.db import get_session

    _enable_report(client_admin)
    data = _seed_report_sites(client_admin)
    site_ids = data["site_ids"]
    department_ids = data["department_ids"]
    diet_names = data["diet_names"]

    login_bound_user(client_admin, site_id=site_ids["a1"])
    client_a2 = client_admin.application.test_client()
    client_a2.environ_base = {}
    login_bound_user(client_a2, site_id=site_ids["a2"])

    engine = get_session().get_bind()
    captured_sql: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        captured_sql.append(statement)

    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        report_a1 = client_admin.get(
            f"/api/report?year={YEAR}&week={WEEK}&site_id={site_ids['a2']}",
            headers={"X-Site-ID": site_ids["a2"]},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)

    assert report_a1.status_code == 200, report_a1.get_data(as_text=True)
    payload_a1 = report_a1.get_json()
    assert [row["department_id"] for row in payload_a1["departments"]] == [
        department_ids["a1"]
    ]
    lunch_a1 = payload_a1["departments"][0]["lunch"]
    assert lunch_a1 == {
        "normal": 9,
        "specials": {diet_names["a1"]: 1},
        "total": 10,
    }
    assert payload_a1["totals"]["lunch"] == {
        "normal": 9,
        "specials": {diet_names["a1"]: 1},
        "total": 10,
    }
    assert not any(
        statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "TRUNCATE "))
        for statement in captured_sql
    )

    report_a2 = client_a2.get(
        f"/api/report?year={YEAR}&week={WEEK}",
        headers={"If-None-Match": report_a1.headers["ETag"]},
    )
    assert report_a2.status_code == 200
    assert report_a2.headers["ETag"] != report_a1.headers["ETag"]
    payload_a2 = report_a2.get_json()
    assert [row["department_id"] for row in payload_a2["departments"]] == [
        department_ids["a2"]
    ]
    assert payload_a2["totals"]["lunch"] == {
        "normal": 19,
        "specials": {diet_names["a2"]: 1},
        "total": 20,
    }

    for foreign_department in (department_ids["a2"], department_ids["b1"]):
        denied = client_admin.get(
            f"/api/report?year={YEAR}&week={WEEK}&department_id={foreign_department}"
        )
        assert denied.status_code == 404

    csv_a1 = client_admin.get(
        f"/api/report/export?year={YEAR}&week={WEEK}&format=csv&site_id={site_ids['a2']}",
        headers={"X-Site-ID": site_ids["a2"]},
    )
    csv_a2 = client_a2.get(
        f"/api/report/export?year={YEAR}&week={WEEK}&format=csv",
        headers={"If-None-Match": csv_a1.headers["ETag"]},
    )
    assert csv_a1.status_code == 200
    assert csv_a2.status_code == 200
    assert csv_a2.headers["ETag"] != csv_a1.headers["ETag"]
    for response, expected_department, expected_name in (
        (csv_a1, department_ids["a1"], diet_names["a1"]),
        (csv_a2, department_ids["a2"], diet_names["a2"]),
    ):
        rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
        department_rows = [row for row in rows if row and row[0] == expected_department]
        assert len(department_rows) == 2
        lunch_row = next(row for row in department_rows if row[2] == "lunch")
        assert json.loads(lunch_row[5]) == {expected_name: 1}
        assert department_ids["b1"] not in response.get_data(as_text=True)

    xlsx_a1 = client_admin.get(
        f"/api/report/export?year={YEAR}&week={WEEK}&format=xlsx"
    )
    xlsx_a2 = client_a2.get(
        f"/api/report/export?year={YEAR}&week={WEEK}&format=xlsx"
    )
    assert xlsx_a1.status_code == xlsx_a2.status_code == 200
    for response, expected_department, foreign_department in (
        (xlsx_a1, department_ids["a1"], department_ids["a2"]),
        (xlsx_a2, department_ids["a2"], department_ids["a1"]),
    ):
        rows = _department_rows_xlsx(response.data)
        department_rows = [row for row in rows if row[0] == expected_department]
        assert len(department_rows) == 2
        assert all(row[0] != foreign_department for row in rows)


@pytest.mark.usefixtures("client_admin")
def test_report_fails_closed_for_noncanonical_stored_diet_reference(client_admin):
    from core.db import get_session
    from tests._auth_site_helpers import login_bound_user

    _enable_report(client_admin)
    data = _seed_report_sites(client_admin)
    department_id = data["department_ids"]["a1"]
    login_bound_user(client_admin, site_id=data["site_ids"]["a1"])
    report_path = f"/api/report?year={YEAR}&week={WEEK}"
    valid_response = client_admin.get(report_path)
    assert valid_response.status_code == 200
    matching_etag = valid_response.headers["ETag"]

    with client_admin.application.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO weekview_registrations("
                    "tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked"
                    ") VALUES(1, :department_id, :year, :week, 3, 'lunch', 'legacy label', 1)"
                ),
                {"department_id": department_id, "year": YEAR, "week": WEEK},
            )
            db.commit()
        finally:
            db.close()

    engine = get_session().get_bind()
    captured_sql = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        captured_sql.append(statement)

    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        response = client_admin.get(
            report_path,
            headers={"If-None-Match": matching_etag},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)

    assert response.status_code == 503
    assert response.get_json()["detail"] == "report_schema_unavailable"
    assert "legacy label" not in response.get_data(as_text=True)
    assert not any(
        statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "TRUNCATE "))
        for statement in captured_sql
    )

    with client_admin.application.app_context():
        db = get_session()
        try:
            row = db.execute(
                text(
                    "SELECT diet_type, marked FROM weekview_registrations "
                    "WHERE department_id=:department_id AND day_of_week=3"
                ),
                {"department_id": department_id},
            ).one()
            assert (row[0], row[1]) == ("legacy label", 1)
            db.execute(
                text(
                    "DELETE FROM weekview_registrations "
                    "WHERE department_id=:department_id AND day_of_week=3"
                ),
                {"department_id": department_id},
            )
            db.commit()
        finally:
            db.close()
