from __future__ import annotations

from datetime import date as _date

from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, SitesRepo
from core.db import get_session
from core.weekview_vm import build_weekview_vm


def _ensure_display_order_column() -> None:
    db = get_session()
    try:
        cols = db.execute(text("PRAGMA table_info('departments')")).fetchall()
        has_col = any(str(c[1]) == "display_order" for c in cols)
        if not has_col:
            db.execute(text("ALTER TABLE departments ADD COLUMN display_order INTEGER NULL"))
            db.commit()
    finally:
        db.close()


def test_department_order_fallback_to_name_when_display_order_missing(app_session):
    _ensure_display_order_column()
    site, _ = SitesRepo().create_site("Order fallback site")
    repo = DepartmentsRepo()
    d_b, _ = repo.create_department(site_id=site["id"], name="Beta", resident_count_mode="fixed", resident_count_fixed=1)
    d_a, _ = repo.create_department(site_id=site["id"], name="Alfa", resident_count_mode="fixed", resident_count_fixed=1)

    db = get_session()
    try:
        db.execute(text("UPDATE departments SET display_order=NULL WHERE id IN (:a,:b)"), {"a": d_a["id"], "b": d_b["id"]})
        db.commit()
    finally:
        db.close()

    rows = repo.list_for_site(site["id"])
    assert [r["name"] for r in rows][:2] == ["Alfa", "Beta"]


def test_department_order_uses_display_order_then_name(app_session):
    _ensure_display_order_column()
    site, _ = SitesRepo().create_site("Order explicit site")
    repo = DepartmentsRepo()
    d_a, _ = repo.create_department(site_id=site["id"], name="Alfa", resident_count_mode="fixed", resident_count_fixed=1)
    d_b, _ = repo.create_department(site_id=site["id"], name="Beta", resident_count_mode="fixed", resident_count_fixed=1)

    db = get_session()
    try:
        db.execute(text("UPDATE departments SET display_order=20 WHERE id=:id"), {"id": d_a["id"]})
        db.execute(text("UPDATE departments SET display_order=10 WHERE id=:id"), {"id": d_b["id"]})
        db.commit()
    finally:
        db.close()

    rows = repo.list_for_site(site["id"])
    assert [r["name"] for r in rows][:2] == ["Beta", "Alfa"]


def test_weekview_vm_departments_follow_display_order(app_session):
    _ensure_display_order_column()
    site, _ = SitesRepo().create_site("Weekview order site")
    repo = DepartmentsRepo()
    d_a, _ = repo.create_department(site_id=site["id"], name="Alfa", resident_count_mode="fixed", resident_count_fixed=1)
    d_b, _ = repo.create_department(site_id=site["id"], name="Beta", resident_count_mode="fixed", resident_count_fixed=1)

    db = get_session()
    try:
        db.execute(text("UPDATE departments SET display_order=50 WHERE id=:id"), {"id": d_a["id"]})
        db.execute(text("UPDATE departments SET display_order=5 WHERE id=:id"), {"id": d_b["id"]})
        db.commit()
    finally:
        db.close()

    iso = _date.today().isocalendar()
    vm = build_weekview_vm(site_id=site["id"], year=int(iso[0]), week=int(iso[1]), tenant_id=1)
    assert [d["name"] for d in vm.get("departments", [])][:2] == ["Beta", "Alfa"]
