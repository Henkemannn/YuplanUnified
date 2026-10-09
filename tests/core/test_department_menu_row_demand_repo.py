from __future__ import annotations

from sqlalchemy import text

from core.db import get_session
from core.department_menu_row_demand_repo import DepartmentMenuRowDemandRepo
from core.models import Department, Site, Tenant


def _seed_prerequisites() -> tuple[int, str, str]:
    tenant_name = "DemandTenant-site-demand"
    db = get_session()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if tenant is None:
            tenant = Tenant(name=tenant_name)
            db.add(tenant)
            db.flush()
        site = db.query(Site).filter(Site.id == "site-demand").first()
        if site is None:
            site = Site(id="site-demand", name="Demand Site", tenant_id=int(tenant.id), version=0)
            db.add(site)
        department = db.query(Department).filter(Department.id == "dept-demand").first()
        if department is None:
            department = Department(
                id="dept-demand",
                site_id="site-demand",
                name="Demand Department",
                resident_count_mode="manual",
                resident_count_fixed=10,
            )
            db.add(department)
        db.commit()
        return int(tenant.id), str(site.id), str(department.id)
    finally:
        db.close()


def test_department_menu_row_demand_repo_upserts_by_row_identity_and_version(app_session):
    tenant_id, site_id, department_id = _seed_prerequisites()
    repo = DepartmentMenuRowDemandRepo()

    with app_session.app_context():
        first = repo.upsert_for_row(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=department_id,
            year=2026,
            week=16,
            weekday=1,
            builder_menu_id="builder-menu-1",
            builder_menu_version=1,
            builder_menu_row_id="builder-menu-1-row-1",
            selection_group_id="group-a",
            quantity=12,
        )
        second = repo.upsert_for_row(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=department_id,
            year=2026,
            week=16,
            weekday=1,
            builder_menu_id="builder-menu-1",
            builder_menu_version=1,
            builder_menu_row_id="builder-menu-1-row-1",
            selection_group_id="group-b",
            quantity=15,
        )
        third = repo.upsert_for_row(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=department_id,
            year=2026,
            week=16,
            weekday=1,
            builder_menu_id="builder-menu-1",
            builder_menu_version=2,
            builder_menu_row_id="builder-menu-1-row-1",
            selection_group_id=None,
            quantity=9,
        )

    assert first["selection_group_id"] == "group-a"
    assert first["quantity"] == 12
    assert second["selection_group_id"] == "group-b"
    assert second["quantity"] == 15
    assert third["selection_group_id"] is None
    assert third["quantity"] == 9

    db = get_session()
    try:
        count = db.execute(
            text(
                "SELECT COUNT(*) FROM department_menu_row_demands "
                "WHERE tenant_id=:tenant_id AND site_id=:site_id AND department_id=:department_id"
            ),
            {"tenant_id": tenant_id, "site_id": site_id, "department_id": department_id},
        ).fetchone()[0]
        assert int(count) == 2

        current = repo.get_for_row(
            tenant_id=tenant_id,
            site_id=site_id,
            department_id=department_id,
            year=2026,
            week=16,
            weekday=1,
            builder_menu_id="builder-menu-1",
            builder_menu_version=1,
            builder_menu_row_id="builder-menu-1-row-1",
        )
        assert current is not None
        assert current["selection_group_id"] == "group-b"
        assert current["quantity"] == 15
    finally:
        db.close()
