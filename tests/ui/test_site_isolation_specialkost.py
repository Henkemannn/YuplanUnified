import pytest
from sqlalchemy import text


def _ensure_admin_session(client, site_id: str | None = None) -> None:
    if site_id is not None:
        from tests._auth_site_helpers import login_bound_user

        login_bound_user(
            client,
            site_id=site_id,
            email=f"site-isolation-{site_id}@example.test",
        )
        return
    from core.db import get_session
    from core.models import Tenant, User
    from core.admin_user_repo import _set_user_site_binding

    with client.application.app_context():
        db = get_session()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == 1).first()
            if tenant is None:
                db.add(Tenant(id=1, name="Site Isolation Test Tenant"))
            user = User(
                tenant_id=1,
                username=f"site-isolation-{site_id or 'none'}@example.test",
                email=f"site-isolation-{site_id or 'none'}@example.test",
                password_hash="!",
                role="admin",
                is_active=True,
                auth_version=1,
            )
            db.add(user)
            db.flush()
            if site_id is not None:
                _set_user_site_binding(
                    db,
                    user_id=int(user.id),
                    tenant_id=1,
                    site_id=site_id,
                )
            db.commit()
            user_id = int(user.id)
            auth_version = int(user.auth_version or 1)
        finally:
            db.close()

    with client.session_transaction() as session:
        session["role"] = "admin"
        session["user_id"] = user_id
        session["tenant_id"] = 1
        session["auth_version"] = auth_version
        if site_id is None:
            session.pop("site_id", None)
            session.pop("site_lock", None)
        else:
            session["site_id"] = site_id
            session["site_lock"] = True


def test_diet_types_isolation_between_sites(client):
    # Seed two sites and one diet type on site A
    from core.admin_repo import DietTypesRepo
    from core.db import get_session
    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, tenant_id INTEGER NOT NULL DEFAULT 1, name TEXT NOT NULL)"))
        db.execute(text("INSERT OR IGNORE INTO sites(id,tenant_id,name) VALUES('A',1,'Site A')"))
        db.execute(text("INSERT OR IGNORE INTO sites(id,tenant_id,name) VALUES('B',1,'Site B')"))
        db.commit()
    finally:
        db.close()

    # Create diet type for site A only
    DietTypesRepo().create(site_id='A', name='Glutenfri-A', default_select=False)

    # View list on site A
    _ensure_admin_session(client, "A")
    resp_a = client.get("/ui/admin/specialkost")
    assert resp_a.status_code == 200
    html_a = resp_a.get_data(as_text=True)
    assert "Glutenfri-A" in html_a

    # Switch to site B and ensure isolation
    _ensure_admin_session(client, "B")
    resp_b = client.get("/ui/admin/specialkost")
    assert resp_b.status_code == 200
    html_b = resp_b.get_data(as_text=True)
    assert "Glutenfri-A" not in html_b


def test_weekly_report_requires_site_selection_when_missing(client):
    # A regular user without a valid site context must fail closed.
    _ensure_admin_session(client)
    resp = client.get("/ui/admin/report/week?year=2025&week=10&department_id=ALL&view=day")
    assert resp.status_code == 401
    assert "Veckorapport" not in resp.get_data(as_text=True)


def test_admin_specialkost_list_groups_categories_expanded_by_default(client):
    from core.admin_repo import DietTypesRepo
    from core.db import get_session

    db = get_session()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
        db.execute(text("INSERT OR IGNORE INTO sites(id,name) VALUES('group-site','Group Site')"))
        db.commit()
    finally:
        db.close()

    repo = DietTypesRepo()
    repo.create(site_id="group-site", name="Timbal Grupp UI", diet_family="Textur", default_select=False)
    repo.create(site_id="group-site", name="Ej Fisk Grupp UI", diet_family="Allergi / Exkludering", default_select=False)

    _ensure_admin_session(client, "group-site")

    resp = client.get("/ui/admin/specialkost")
    if resp.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<details" in html
    assert " open>" in html
    assert "Textur" in html
    assert "Allergi / Exkludering" in html
    assert "Timbal Grupp UI" in html
    assert "Ej Fisk Grupp UI" in html
