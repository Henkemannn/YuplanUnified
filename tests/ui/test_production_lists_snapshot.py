from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import text

from core.admin_repo import SitesRepo
from core.db import get_session
from core.production_lists_repo import ProductionListsRepo


def _h(role: str = "admin") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _set_active_site(client, site_id: str) -> None:
    with client.session_transaction() as sess:
        sess["site_id"] = site_id


def test_create_production_list_snapshot(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    payload = {
        "site_id": site["id"],
        "date": "2026-02-10",
        "meal_type": "lunch",
        "payload": {
            "year": 2026,
            "week": 7,
            "day_label": "Tis",
            "meal_label": "Lunch",
            "normal": {"rows": [], "alt1_total": 0, "alt2_total": 0, "total": 0},
            "special": {"worklist": []},
        },
    }
    resp = client_admin.post("/api/production-lists", headers=_h(), json=payload)
    assert resp.status_code == 201
    body = resp.get_json() or {}
    assert body.get("ok") is True
    assert (body.get("item") or {}).get("id")


def test_production_list_renders(app_session, client_admin):
    site, _ = SitesRepo().create_site(f"Prod list render site {uuid.uuid4()}")
    _set_active_site(client_admin, site["id"])

    item = ProductionListsRepo().create_snapshot(
        site_id=site["id"],
        date_iso="2026-02-11",
        meal_type="lunch",
        payload={
            "week": 7,
            "day_label": "Ons",
            "meal": "lunch",
            "meal_label": "Lunch",
            "dishes": {"alt1": "Pasta", "alt2": "Fisk"},
            "normal": {
                "rows": [
                    {"department_name": "Avd A", "alt_choice": "alt1", "count": 4},
                    {"department_name": "Avd B", "alt_choice": "alt2", "count": 2},
                ],
                "alt1_total": 4,
                "alt2_total": 2,
            },
            "special": {
                "worklist": [
                    {
                        "diet_type_name": "Glutenfri",
                        "total": 2,
                        "rows": [{"department_name": "Avd A", "count": 2, "alt_label": "Alt1"}],
                    }
                ]
            },
            "service_addon": {
                "addon_name": "Mos",
                "total_count": 3,
                "departments": [{"department_name": "Avd A", "count": 3, "note": "Extra"}],
            },
        },
    )

    rv = client_admin.get(f"/ui/production-lists/{item['id']}?site_id={site['id']}", headers=_h())
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert "Tillagningslista" in html
    assert "Glutenfri" in html
    assert "Serveringstillägg" in html


def test_old_lists_cleanup(app_session):
    site, _ = SitesRepo().create_site(f"Prod list cleanup site {uuid.uuid4()}")
    repo = ProductionListsRepo()

    fresh = repo.create_snapshot(
        site_id=site["id"],
        date_iso="2026-02-12",
        meal_type="dinner",
        payload={"meal": "dinner"},
    )

    db = get_session()
    try:
        db.execute(
            text(
                """
                INSERT INTO production_lists(id, site_id, created_at, date, meal_type, payload_json)
                VALUES(:id, :site_id, :created_at, :date, :meal_type, :payload_json)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "site_id": site["id"],
                "created_at": (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S"),
                "date": "2026-01-01",
                "meal_type": "lunch",
                "payload_json": "{}",
            },
        )
        db.commit()
    finally:
        db.close()

    items = repo.list_for_site(site["id"])
    ids = {it["id"] for it in items}
    assert fresh["id"] in ids
    assert len(items) == 1
