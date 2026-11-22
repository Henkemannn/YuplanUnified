from __future__ import annotations

from datetime import date

from core.db import get_new_session
from core.models import Dish, ServiceMetric, Site, Task
from core.service_metrics_service import ServiceMetricsService


SITE_A = "site-a"
SITE_B = "site-b"


def _seed_references() -> tuple[int, int, int]:
    db = get_new_session()
    try:
        if db.get(Site, SITE_A) is None:
            db.add(Site(id=SITE_A, tenant_id=1, name="Site A"))
        if db.get(Site, SITE_B) is None:
            db.add(Site(id=SITE_B, tenant_id=2, name="Site B"))
        for dish_id, tenant_id, site_id, name in [
            (9101, 1, SITE_A, "Same site"),
            (9102, 1, SITE_B, "Other site"),
            (9103, 2, SITE_B, "Other tenant"),
            (9104, 1, None, "Legacy"),
        ]:
            if db.get(Dish, dish_id) is None:
                db.add(Dish(id=dish_id, tenant_id=tenant_id, site_id=site_id, name=name, category=None))
        task = Task(
            tenant_id=1,
            task_type="prep",
            title="Dish task",
            done=False,
            creator_user_id=1,
        )
        db.add(task)
        db.commit()
        return task.id, 9101, 9102
    finally:
        db.close()


def _session_for(client, *, site_id: str | None = SITE_A) -> None:
    client.environ_base = {"HTTP_X_USER_ROLE": "admin"}
    with client.session_transaction() as session:
        session.update(
            {
                "user_id": 1,
                "role": "admin",
                "tenant_id": 1,
                "site_id": site_id,
                "auth_version": 1,
            }
        )


def test_task_dish_rejects_non_site_dish_without_write(app_session):
    task_id, same_site_dish, other_site_dish = _seed_references()
    client = app_session.test_client()
    _session_for(client)

    accepted = client.patch(f"/tasks/{task_id}", json={"dish_id": same_site_dish})
    assert accepted.status_code == 200

    rejected = client.patch(f"/tasks/{task_id}", json={"dish_id": other_site_dish})
    assert rejected.status_code == 403

    db = get_new_session()
    try:
        assert db.get(Task, task_id).dish_id == same_site_dish
    finally:
        db.close()


def test_service_metrics_rejects_invalid_dish_and_accepts_category_only(app_session):
    _seed_references()
    service = ServiceMetricsService()
    base = {
        "unit_id": 1,
        "date": "2026-01-05",
        "meal": "lunch",
        "guest_count": 5,
        "produced_qty_kg": 1.0,
    }

    valid = service.ingest(1, [{**base, "dish_id": 9101}], site_id=SITE_A)
    assert valid == {"ok": True, "inserted": 1, "updated": 0, "errors": []}

    invalid = service.ingest(1, [{**base, "dish_id": 9102}], site_id=SITE_A)
    assert invalid["inserted"] == 0
    assert invalid["errors"] == ["dish_site_mismatch"]

    for rejected_dish, error in [
        (9103, "dish_tenant_mismatch"),
        (9104, "dish_site_mismatch"),
        (999999, "dish_not_found"),
    ]:
        rejected = service.ingest(
            1,
            [{**base, "date": "2026-01-07", "dish_id": rejected_dish}],
            site_id=SITE_A,
        )
        assert rejected["inserted"] == 0
        assert rejected["errors"] == [error]

    category_only = service.ingest(
        1,
        [{**base, "date": "2026-01-06", "dish_id": None, "category": "soup"}],
    )
    assert category_only == {"ok": True, "inserted": 1, "updated": 0, "errors": []}

    db = get_new_session()
    try:
        assert db.query(ServiceMetric).filter(ServiceMetric.date == date(2026, 1, 5)).count() == 1
        assert db.query(ServiceMetric).filter(ServiceMetric.date == date(2026, 1, 6)).count() == 1
    finally:
        db.close()
