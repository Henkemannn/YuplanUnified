import pytest
from sqlalchemy import text

HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        # Robust insert: avoid collisions on unique name or id
        conn.execute(
            text("INSERT OR IGNORE INTO sites (id, name) VALUES (:id, :name)"),
            {"id": "00000000-0000-0000-0000-000000000000", "name": "Test Site"},
        )
        conn.commit()
    finally:
        conn.close()


def test_planering_v1_empty_state(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Välj dag och måltid" in html


def test_planering_v1_selected_state(app_session):
    client = app_session.test_client()
    _seed_basics()
    site_id = "00000000-0000-0000-0000-000000000000"
    # Seed a department and a diet type with defaults so the checklist has options
    from core.admin_repo import DepartmentsRepo, DietTypesRepo
    drepo = DepartmentsRepo()
    dep, _v = drepo.create_department(site_id, "Avd 1", "fixed", 10)
    trepo = DietTypesRepo()
    dt_id = trepo.create(site_id=site_id, name="Glutenfri", default_select=False)
    ver = drepo.get_version(dep["id"]) or 0
    drepo.upsert_department_diet_defaults(dep["id"], ver, [{"diet_type_id": str(dt_id), "default_count": 3}])

    # First request: selected day+meal should render checklist UI immediately (wizard step 3)
    rv = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert "Tillagningslista" in html
    assert "name=\"selected_diets\"" in html or "name=\"selected_diets\"" in html

    # Second request: with a selected diet, adaptation list should render
    rv2 = client.get(f"/ui/kitchen/planering?site_id={site_id}&day=0&meal=lunch&selected_diets={dt_id}", headers=HEADERS)
    assert rv2.status_code == 200
    html2 = rv2.data.decode("utf-8")
    assert "Anpassningslista" in html2
    assert "Avd 1" in html2
