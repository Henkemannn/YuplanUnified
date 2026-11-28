from __future__ import annotations

import uuid

from sqlalchemy import text


def test_legacy_diet_api_uses_authenticated_site_and_fails_closed_for_units(
    app_session, client_admin
) -> None:
    from core.db import get_session
    from core.diet_service import DietService
    from core.models import DietaryType, Unit, UnitDietAssignment

    suffix = uuid.uuid4().hex
    site_a1 = f"legacy-diet-a1-{suffix}"
    site_a2 = f"legacy-diet-a2-{suffix}"
    site_b1 = f"legacy-diet-b1-{suffix}"
    diet_ids: list[int] = []
    unit_ids: list[int] = []
    assignment_ids: list[int] = []
    created_diet_id: int | None = None

    with app_session.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO tenants(id, name, active) "
                    "VALUES (2, 'Legacy diet tenant B', 1) ON CONFLICT(id) DO NOTHING"
                )
            )
            db.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id) VALUES "
                    "(:site_a1, 'Legacy diet A1', 1), "
                    "(:site_a2, 'Legacy diet A2', 1), "
                    "(:site_b1, 'Legacy diet B1', 2)"
                ),
                {"site_a1": site_a1, "site_a2": site_a2, "site_b1": site_b1},
            )
            db.commit()
        finally:
            db.close()

        service = DietService()
        diet_a1 = service.create_diet_type(
            1, "Legacy diet A1", site_id=site_a1
        )
        diet_a2 = service.create_diet_type(
            1, "Legacy diet A2", site_id=site_a2
        )
        diet_b1 = service.create_diet_type(
            2, "Legacy diet B1", site_id=site_b1
        )
        diet_ids.extend((diet_a1, diet_a2, diet_b1))

        db = get_session()
        try:
            units = [
                Unit(tenant_id=1, name=f"Legacy unit A1 {suffix}", default_attendance=10),
                Unit(tenant_id=1, name=f"Legacy unit A2 {suffix}", default_attendance=20),
                Unit(tenant_id=2, name=f"Legacy unit B1 {suffix}", default_attendance=30),
            ]
            db.add_all(units)
            db.flush()
            unit_ids.extend(unit.id for unit in units)
            assignments = [
                UnitDietAssignment(
                    unit_id=units[0].id, dietary_type_id=diet_a1, count=11
                ),
                UnitDietAssignment(
                    unit_id=units[1].id, dietary_type_id=diet_a2, count=22
                ),
                UnitDietAssignment(
                    unit_id=units[2].id, dietary_type_id=diet_b1, count=33
                ),
            ]
            db.add_all(assignments)
            db.flush()
            assignment_ids.extend(assignment.id for assignment in assignments)
            db.commit()
        finally:
            db.close()

    with client_admin.session_transaction() as session:
        session["user_id"] = 990601
        session["role"] = "admin"
        session["tenant_id"] = 1
        session["site_id"] = site_a1
        session["auth_version"] = 1

    headers = {"X-User-Role": "admin"}
    try:
        types_response = client_admin.get(
            f"/diet/types?site_id={site_a2}",
            headers={**headers, "X-Site-ID": site_a2},
        )
        assert types_response.status_code == 200
        assert [
            row["id"] for row in types_response.get_json()["diet_types"]
        ] == [diet_a1]

        create_response = client_admin.post(
            "/diet/types",
            headers=headers,
            json={
                "name": "Created by A1",
                "default_select": False,
                "site_id": site_a2,
            },
        )
        assert create_response.status_code == 200
        created_diet_id = create_response.get_json()["diet_type_id"]

        update_other_site = client_admin.post(
            f"/diet/types/{diet_a2}",
            headers=headers,
            json={"name": "Cross-site update"},
        )
        delete_other_site = client_admin.delete(
            f"/diet/types/{diet_a2}", headers=headers
        )
        assert update_other_site.status_code == 404
        assert delete_other_site.status_code == 404
        delete_assigned_type = client_admin.delete(
            f"/diet/types/{diet_a1}", headers=headers
        )
        assert delete_assigned_type.status_code == 409

        update_other_tenant = client_admin.post(
            f"/diet/types/{diet_b1}",
            headers=headers,
            json={"name": "Cross-tenant update"},
        )
        delete_other_tenant = client_admin.delete(
            f"/diet/types/{diet_b1}", headers=headers
        )
        assert update_other_tenant.status_code == 404
        assert delete_other_tenant.status_code == 404

        with app_session.app_context():
            db = get_session()
            try:
                created = db.execute(
                    text("SELECT site_id, name FROM dietary_types WHERE id=:id"),
                    {"id": created_diet_id},
                ).one()
                assert created == (site_a1, "Created by A1")
                assert db.execute(
                    text("SELECT name FROM dietary_types WHERE id=:id"),
                    {"id": diet_a2},
                ).scalar_one() == "Legacy diet A2"
                assert db.execute(
                    text(
                        "SELECT count FROM unit_diet_assignments "
                        "WHERE id=:assignment_id"
                    ),
                    {"assignment_id": assignment_ids[0]},
                ).scalar_one() == 11
                assert db.execute(
                    text("SELECT name FROM dietary_types WHERE id=:id"),
                    {"id": diet_b1},
                ).scalar_one() == "Legacy diet B1"
            finally:
                db.close()

        for path, method, payload in (
            ("/diet/units", "GET", None),
            (f"/diet/assignments?unit={unit_ids[1]}", "GET", None),
            (
                "/diet/assignments",
                "POST",
                {
                    "unit_id": unit_ids[2],
                    "diet_type_id": diet_b1,
                    "count": 99,
                },
            ),
            (f"/diet/assignments/{assignment_ids[2]}", "DELETE", None),
        ):
            response = client_admin.open(
                path, method=method, headers=headers, json=payload
            )
            assert response.status_code == 403
            assert response.get_json()["detail"] == "unit_site_scope_unavailable"

        with app_session.app_context():
            db = get_session()
            try:
                assert db.execute(
                    text(
                        "SELECT id, unit_id, dietary_type_id, count "
                        "FROM unit_diet_assignments WHERE id IN (:a1, :a2, :b1) "
                        "ORDER BY id"
                    ),
                    {
                        "a1": assignment_ids[0],
                        "a2": assignment_ids[1],
                        "b1": assignment_ids[2],
                    },
                ).all() == [
                    (assignment_ids[0], unit_ids[0], diet_a1, 11),
                    (assignment_ids[1], unit_ids[1], diet_a2, 22),
                    (assignment_ids[2], unit_ids[2], diet_b1, 33),
                ]
            finally:
                db.close()
    finally:
        with app_session.app_context():
            db = get_session()
            try:
                db.query(UnitDietAssignment).filter(
                    UnitDietAssignment.id.in_(assignment_ids)
                ).delete(synchronize_session=False)
                db.query(Unit).filter(Unit.id.in_(unit_ids)).delete(
                    synchronize_session=False
                )
                db.query(UnitDietAssignment).filter(
                    UnitDietAssignment.dietary_type_id.in_(
                        diet_ids + ([created_diet_id] if created_diet_id else [])
                    )
                ).delete(synchronize_session=False)
                db.query(DietaryType).filter(
                    DietaryType.id.in_(
                        diet_ids + ([created_diet_id] if created_diet_id else [])
                    )
                ).delete(synchronize_session=False)
                db.execute(
                    text(
                        "DELETE FROM sites WHERE id IN (:site_a1, :site_a2, :site_b1)"
                    ),
                    {"site_a1": site_a1, "site_a2": site_a2, "site_b1": site_b1},
                )
                db.commit()
            finally:
                db.close()
