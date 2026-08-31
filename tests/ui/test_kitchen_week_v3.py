from flask.testing import FlaskClient
from sqlalchemy import text
from datetime import date as _date
from pathlib import Path
import uuid
import re

from core.db import get_session
from core.admin_repo import DietTypesRepo, Alt2Repo
from core.department_menu_choice_repo import MenuChoiceRepo


def _seed_site_and_departments(db, site_id: str, deps: list[tuple[str, str, int]]):
    if not db.execute(text("SELECT 1 FROM sites WHERE id=:i"), {"i": site_id}).fetchone():
        db.execute(text("INSERT INTO sites(id,name) VALUES(:i,:n)"), {"i": site_id, "n": f"K3 {site_id}"})
    cols = {r[1] for r in db.execute(text("PRAGMA table_info('departments')")).fetchall()}
    for dep_id, dep_name, rc in deps:
        if not db.execute(text("SELECT 1 FROM departments WHERE id=:i"), {"i": dep_id}).fetchone():
            if {"resident_count_mode", "resident_count_fixed", "version"}.issubset(cols):
                db.execute(
                    text("INSERT INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version) VALUES(:i,:s,:n,'fixed',:c,0)"),
                    {"i": dep_id, "s": site_id, "n": dep_name, "c": int(rc)},
                )
            else:
                db.execute(text("INSERT INTO departments(id,site_id,name) VALUES(:i,:s,:n)"), {"i": dep_id, "s": site_id, "n": dep_name})
    db.commit()


def _link_diets(db, dept_id: str, items: list[tuple[str, int]]):
    # Create table if missing
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS department_diet_defaults (
            department_id TEXT NOT NULL,
            diet_type_id TEXT NOT NULL,
            default_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (department_id, diet_type_id)
        )
    """))
    for diet_type_id, default_count in items:
        db.execute(
            text("""
                INSERT INTO department_diet_defaults(department_id, diet_type_id, default_count)
                VALUES(:d,:t,:c)
                ON CONFLICT(department_id, diet_type_id) DO UPDATE SET default_count=excluded.default_count
            """),
            {"d": dept_id, "t": str(diet_type_id), "c": int(default_count)},
        )
    db.commit()


def test_kitchen_week_v3_renders_and_flags(app_session):
    app = app_session
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        db = get_session()
        try:
            site_id = f"site-k3-{suffix}"
            dep1 = (f"dep-1-{suffix}", f"Avd Ett {suffix}", 12)
            dep2 = (f"dep-2-{suffix}", f"Avd Två {suffix}", 9)
            _seed_site_and_departments(db, site_id, [dep1, dep2])
            # Create diet types
            dt_repo = DietTypesRepo()
            dt1 = dt_repo.create(site_id=site_id, name=f"Glutenfri {site_id}", default_select=False)
            dt2 = dt_repo.create(site_id=site_id, name=f"Laktosfri {site_id}", default_select=False)
            # Link dt1 only to dep1; dt2 only to dep2
            _link_diets(db, dep1[0], [(dt1, 2)])
            _link_diets(db, dep2[0], [(dt2, 1)])
            # Seed canonical explicit Alt2 for dep1, week 5, Monday.
            MenuChoiceRepo().set_choice(
                tenant_id=1,
                site_id=site_id,
                department_id=dep1[0],
                year=2026,
                week=5,
                weekday=1,
                selected_alt="Alt2",
            )
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    # Ensure session site context points to our seeded site
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
    rv = client.get(f"/ui/kitchen/week?year=2026&week=5", headers=headers)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Department names and presence of Boende row in the grid (not header pill)
    assert "Avd Ett" in html
    assert "Avd Två" in html
    assert "<tr class=\"boende-row\">" in html or "Boende</td>" in html
    # Diet names scoped per department
    assert "Glutenfri" in html
    assert "Laktosfri" in html
    # Buttons contain dataset attributes
    assert "class=\"kostcell-btn" in html and "data-department-id" in html and "data-diet-type-id" in html
    # Buttons should not render disabled in the markup
    assert not re.search(r"kostcell-btn[^>]*\sdisabled", html)
    # Alt2 flag appears at least once (Monday lunch for dep1)
    assert "is-alt2" in html
    # JS wiring include for done-mark toggle
    assert "kitchen_week_v3.js" in html
    assert "src=\"/static/js/kitchen_week_v3.js\"" in html
    # Menu modal container + JS include for fetch/inject
    assert 'id="menuModal"' in html
    assert "js/menu_modal.js" in html
    # Print-friendly header + print action
    assert "print-header" in html
    assert "data-action=\"print\"" in html
    assert re.search(r"class=\"no-print\"[^>]*>\s*<h1 class=\"app-shell__title\">Kök – Veckovy<", html)
    # Ensure legacy CSS does not leak into app shell
    assert "unified_ui.css" not in html
    assert "unified_cook.css" not in html
    # Ensure CSS allows pointer events on kostcell buttons
    css_text = Path("static/css/kitchen_week_v3.css").read_text(encoding="utf-8")
    assert "pointer-events: auto" in css_text
    assert not re.search(r"\.kostcell-btn\s*\{[^}]*pointer-events:\s*none", css_text)
    assert "var(--yp-alt2-bg)" in css_text
    # Only Veckovy should be active in kitchen nav on weekview
    assert html.count("app-shell__nav-item--active") == 1
    assert re.search(r"app-shell__nav-item--active[^>]*>\s*Veckovy\s*<", html)


def test_kitchen_week_v3_canonical_alt2_beats_stale_legacy_flags(app_session):
    app = app_session
    week = 7
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        db = get_session()
        try:
            site_id = f"site-k3-canonical-{suffix}"
            dep = (f"dep-k3-canonical-{suffix}", f"Avd Canon {suffix}", 10)
            _seed_site_and_departments(db, site_id, [dep])
            dt_repo = DietTypesRepo()
            dt = dt_repo.create(site_id=site_id, name=f"Glutenfri {site_id}", default_select=False)
            _link_diets(db, dep[0], [(dt, 2)])
            # Stale legacy flag must never override canonical None/Alt1.
            Alt2Repo().bulk_upsert([{"site_id": site_id, "department_id": dep[0], "week": week, "weekday": 1, "enabled": True}])
            choice_repo = MenuChoiceRepo()
            choice_repo.set_choice(
                tenant_id=1,
                site_id=site_id,
                department_id=dep[0],
                year=2026,
                week=week,
                weekday=1,
                selected_alt="Alt2",
            )
        finally:
            db.close()

    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id

    rv_alt2 = client.get(f"/ui/kitchen/week?year=2026&week={week}", headers=headers)
    assert rv_alt2.status_code == 200
    html_alt2 = rv_alt2.data.decode("utf-8")
    assert "is-alt2" in html_alt2

    with app.app_context():
        db = get_session()
        try:
            choice_repo = MenuChoiceRepo()
            choice_repo.set_choice(
                tenant_id=1,
                site_id=site_id,
                department_id=dep[0],
                year=2026,
                week=week,
                weekday=1,
                selected_alt="Alt1",
            )
            db.commit()
        finally:
            db.close()

    rv_alt1 = client.get(f"/ui/kitchen/week?year=2026&week={week}", headers=headers)
    assert rv_alt1.status_code == 200
    html_alt1 = rv_alt1.data.decode("utf-8")
    assert "is-alt2" not in html_alt1

    with app.app_context():
        db = get_session()
        try:
            db.execute(
                text("DELETE FROM department_menu_choices WHERE tenant_id=1 AND site_id=:s AND department_id=:d AND year=2026 AND week=:w AND weekday=1 AND meal='lunch'"),
                {"s": site_id, "d": dep[0], "w": week},
            )
            db.commit()
        finally:
            db.close()

    rv_none = client.get(f"/ui/kitchen/week?year=2026&week={week}", headers=headers)
    assert rv_none.status_code == 200
    html_none = rv_none.data.decode("utf-8")
    assert "is-alt2" not in html_none


def test_kitchen_week_v3_mark_toggle(app_session):
    app = app_session
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        db = get_session()
        try:
            site_id = str(uuid.uuid4())
            dep = (str(uuid.uuid4()), f"Avd Tre {suffix}", 10)
            _seed_site_and_departments(db, site_id, [dep])
            dt_repo = DietTypesRepo()
            dt = dt_repo.create(site_id=site_id, name=f"Glutenfri {site_id}", default_select=False)
            _link_diets(db, dep[0], [(dt, 2)])
        finally:
            db.close()
    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    # Get page
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id
    rv = client.get(f"/ui/kitchen/week?year=2026&week=6", headers=headers)
    assert rv.status_code == 200
    # Fetch ETag and mark Monday lunch
    etag_resp = client.get(f"/api/weekview/etag?department_id={dep[0]}&year=2026&week=6", headers=headers)
    assert etag_resp.status_code == 200
    etag = etag_resp.get_json().get("etag")
    assert etag
    payload = {
        "year": 2026,
        "week": 6,
        "department_id": dep[0],
        "diet_type_id": str(dt),
        "meal": "lunch",
        "weekday_abbr": "Mån",
        "marked": True,
    }
    resp2 = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**headers, "If-Match": etag})
    assert resp2.status_code == 200
    # Refresh page and expect is-done class to appear at least once
    rv2 = client.get(f"/ui/kitchen/week?year=2026&week=6", headers=headers)
    assert rv2.status_code == 200
    html2 = rv2.data.decode("utf-8")
    assert "is-done" in html2


def test_kitchen_week_v3_default_select_premarked_cells(app_session):
    app = app_session
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        db = get_session()
        try:
            site_id = f"site-k3-default-on-{suffix}"
            dep = (f"dep-k3-default-on-{suffix}", f"Avd Default On {suffix}", 11)
            _seed_site_and_departments(db, site_id, [dep])
            dt_repo = DietTypesRepo()
            dt = dt_repo.create(site_id=site_id, name=f"Timbal {site_id}", default_select=True)
            _link_diets(db, dep[0], [(dt, 3)])
        finally:
            db.close()

    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id

    rv = client.get("/ui/kitchen/week?year=2026&week=8", headers=headers)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert re.search(
        rf'<button[^>]*class="[^"]*kostcell-btn[^"]*is-done[^"]*"(?=[^>]*data-department-id="{dep[0]}")(?=[^>]*data-diet-type-id="{dt}")(?=[^>]*data-day-index="1")(?=[^>]*data-meal="lunch")[^>]*>',
        html,
    )


def test_kitchen_week_v3_default_select_false_not_premarked_cells(app_session):
    app = app_session
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        db = get_session()
        try:
            site_id = f"site-k3-default-off-{suffix}"
            dep = (f"dep-k3-default-off-{suffix}", f"Avd Default Off {suffix}", 11)
            _seed_site_and_departments(db, site_id, [dep])
            dt_repo = DietTypesRepo()
            dt = dt_repo.create(site_id=site_id, name=f"Timbal Off {site_id}", default_select=False)
            _link_diets(db, dep[0], [(dt, 3)])
        finally:
            db.close()

    client: FlaskClient = app.test_client()
    headers = {"X-User-Role": "cook", "X-Tenant-Id": "1"}
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["site_id"] = site_id

    rv = client.get("/ui/kitchen/week?year=2026&week=8", headers=headers)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    assert not re.search(
        rf'<button[^>]*class="[^"]*kostcell-btn[^"]*is-done[^"]*"(?=[^>]*data-department-id="{dep[0]}")(?=[^>]*data-diet-type-id="{dt}")(?=[^>]*data-day-index="1")(?=[^>]*data-meal="lunch")[^>]*>',
        html,
    )
