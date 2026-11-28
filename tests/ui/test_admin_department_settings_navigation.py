import uuid
from sqlalchemy import event, text

HEADERS_SUPERUSER = {"X-User-Role": "superuser", "X-Tenant-Id": "1"}
HEADERS_ADMIN = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
HEADERS_USER = {"X-User-Role": "user", "X-Tenant-Id": "1"}


def _seed_site_and_department():
    from core.db import get_session
    from core.admin_repo import DietTypesRepo

    db = get_session()
    try:
        site_id = str(uuid.uuid4())
        dep_id = str(uuid.uuid4())
        db.execute(
            text("INSERT INTO sites(id, tenant_id, name, version) VALUES(:i,1,:n,0)"),
            {"i": site_id, "n": "SiteNav"},
        )
        db.execute(text("INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES(:i,:s,:n,'fixed',5,'',0)"), {"i": dep_id, "s": site_id, "n": "Avd Nav"})
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS department_diet_defaults ("
                "department_id TEXT NOT NULL, "
                "diet_type_id INTEGER NOT NULL REFERENCES dietary_types(id), "
                "default_count INTEGER NOT NULL DEFAULT 0, "
                "PRIMARY KEY(department_id, diet_type_id))"
            )
        )
        db.commit()
    finally:
        db.close()
    diet_id = DietTypesRepo().create(
        site_id=site_id,
        tenant_id=1,
        name="Gluten",
        semantics="atomic",
    )
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT INTO department_diet_defaults("
                "department_id, diet_type_id, default_count"
                ") VALUES(:department_id,:diet_id,1)"
            ),
            {"department_id": dep_id, "diet_id": diet_id},
        )
        db.commit()
    finally:
        db.close()
    return site_id, dep_id, diet_id


def test_systemadmin_shows_settings_link(app_session):
    client = app_session.test_client()
    site_id, dep_id, _diet_id = _seed_site_and_department()

    # View systemadmin page as superuser
    r_sys = client.get(f"/ui/admin/system?site_id={site_id}", headers=HEADERS_SUPERUSER)
    assert r_sys.status_code == 200
    html = r_sys.get_data(as_text=True)
    assert "Systemadministration" in html
    assert "Avd Nav" in html
    # The settings link should be present
    assert f"/ui/admin/departments/{dep_id}/settings" in html

    # Follow settings link as admin
    from tests._auth_site_helpers import login_bound_user

    login_bound_user(client, site_id=site_id)
    r_settings = client.get(f"/ui/admin/departments/{dep_id}/settings")
    assert r_settings.status_code == 200
    shtml = r_settings.get_data(as_text=True)
    assert "Avdelningsinställningar" in shtml
    assert "Boendeantal" in shtml
    assert "Specialkost" in shtml or "Specialkost på avdelningen" in shtml
    assert "Faktaruta" in shtml or "Faktaruta / särskild info" in shtml


def test_settings_rbac_denied_for_non_admin(app_session):
    client = app_session.test_client()
    site_id, dep_id, _diet_id = _seed_site_and_department()

    r_settings = client.get(f"/ui/admin/departments/{dep_id}/settings", headers=HEADERS_USER)
    assert r_settings.status_code in (302, 403, 401)


def _seed_other_tenant_department():
    from core.admin_repo import DietTypesRepo
    from core.db import get_session
    from core.models import Tenant

    site_id = str(uuid.uuid4())
    department_id = str(uuid.uuid4())
    db = get_session()
    try:
        tenant = Tenant(name=f"Settings Tenant {uuid.uuid4()}")
        db.add(tenant)
        db.flush()
        tenant_id = int(tenant.id)
        db.execute(
            text(
                "INSERT INTO sites(id, tenant_id, name, version) "
                "VALUES(:site_id,:tenant_id,'Foreign Settings Site',0)"
            ),
            {"site_id": site_id, "tenant_id": tenant_id},
        )
        db.execute(
            text(
                "INSERT INTO departments("
                "id, site_id, name, resident_count_mode, resident_count_fixed, version"
                ") VALUES(:department_id,:site_id,'Foreign Settings Department','fixed',5,0)"
            ),
            {"department_id": department_id, "site_id": site_id},
        )
        db.commit()
    finally:
        db.close()
    diet_id = DietTypesRepo().create(
        site_id=site_id,
        tenant_id=tenant_id,
        name="Foreign Gluten",
        semantics="atomic",
    )
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT INTO department_diet_defaults("
                "department_id, diet_type_id, default_count"
                ") VALUES(:department_id,:diet_id,2)"
            ),
            {"department_id": department_id, "diet_id": diet_id},
        )
        db.commit()
    finally:
        db.close()
    return department_id, diet_id


def test_settings_are_site_scoped_and_require_csrf(app_session, monkeypatch):
    from tests._auth_site_helpers import login_bound_user
    from core.db import get_session

    client = app_session.test_client()
    site_a1, department_a1, diet_a1 = _seed_site_and_department()
    site_a2, department_a2, diet_a2 = _seed_site_and_department()
    department_b1, diet_b1 = _seed_other_tenant_department()
    login_bound_user(client, site_id=site_a1)

    response = client.get(f"/ui/admin/departments/{department_a1}/settings")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Gluten" in page
    assert f'value="{diet_a1}"' in page

    token = "settings-test-csrf-token"
    with client.session_transaction() as session:
        session["CSRF_TOKEN"] = token
    monkeypatch.setitem(app_session.config, "STRICT_CSRF_IN_TESTS", True)

    form = {
        "residents_base_count": "5",
        "notes": "Scoped update",
        "diet_type_id[]": str(diet_a1),
        "planned_count[]": "3",
    }
    engine = get_session().get_bind()
    captured_sql = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        captured_sql.append(statement)

    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        missing_token = client.post(
            f"/ui/admin/departments/{department_a1}/settings",
            data=form,
        )
        assert missing_token.status_code == 403
        invalid_token = client.post(
            f"/ui/admin/departments/{department_a1}/settings",
            data=form,
            headers={"X-CSRF-Token": "invalid-settings-test-token"},
        )
        assert invalid_token.status_code == 403

        for foreign_department in (department_a2, department_b1):
            assert (
                client.get(f"/ui/admin/departments/{foreign_department}/settings").status_code
                == 403
            )
            foreign_post = client.post(
                f"/ui/admin/departments/{foreign_department}/settings",
                data={
                    **form,
                    "diet_type_id[]": str(
                        diet_a2 if foreign_department == department_a2 else diet_b1
                    ),
                },
                headers={"X-CSRF-Token": token},
            )
            assert foreign_post.status_code == 403

        with app_session.app_context():
            db = get_session()
            try:
                unchanged_count = db.execute(
                    text(
                        "SELECT default_count FROM department_diet_defaults "
                        "WHERE department_id=:department_id AND diet_type_id=:diet_id"
                    ),
                    {"department_id": department_a1, "diet_id": diet_a1},
                ).scalar_one()
                assert unchanged_count == 1
            finally:
                db.close()

        saved = client.post(
            f"/ui/admin/departments/{department_a1}/settings",
            data=form,
            headers={"X-CSRF-Token": token},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)

    assert saved.status_code == 302
    print("SQL_CAPTURE_ADMIN_SETTINGS_SQLITE_BEGIN")
    for statement in captured_sql:
        print(statement)
    print("SQL_CAPTURE_ADMIN_SETTINGS_SQLITE_END")
    assert not any(
        statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "TRUNCATE "))
        for statement in captured_sql
    )
    with app_session.app_context():
        db = get_session()
        try:
            count_a1 = db.execute(
                text(
                    "SELECT default_count FROM department_diet_defaults "
                    "WHERE department_id=:department_id AND diet_type_id=:diet_id"
                ),
                {"department_id": department_a1, "diet_id": diet_a1},
            ).scalar_one()
            count_a2 = db.execute(
                text(
                    "SELECT default_count FROM department_diet_defaults "
                    "WHERE department_id=:department_id AND diet_type_id=:diet_id"
                ),
                {"department_id": department_a2, "diet_id": diet_a2},
            ).scalar_one()
            count_b1 = db.execute(
                text(
                    "SELECT default_count FROM department_diet_defaults "
                    "WHERE department_id=:department_id AND diet_type_id=:diet_id"
                ),
                {"department_id": department_b1, "diet_id": diet_b1},
            ).scalar_one()
            assert (count_a1, count_a2, count_b1) == (3, 1, 2)
        finally:
            db.close()
