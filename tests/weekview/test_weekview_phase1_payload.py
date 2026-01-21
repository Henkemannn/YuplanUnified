import uuid

import pytest

ETAG_RE = __import__("re").compile(r'^W/"weekview:dept:.*:year:\d{4}:week:\d{1,2}:v\d+"$')


def _get(client, role, path):
    return client.get(path, headers={"X-User-Role": role, "X-Tenant-Id": "1"})


def _patch(client, role, path, json=None, extra_headers=None):
    headers = {"X-User-Role": role, "X-Tenant-Id": "1"}
    if extra_headers:
        headers.update(extra_headers)
    return client.patch(path, json=json or {}, headers=headers)


@pytest.fixture
def enable_weekview(client_admin):
    resp = client_admin.post(
        "/features/set",
        json={"name": "ff.weekview.enabled", "enabled": True},
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )
    assert resp.status_code == 200


@pytest.mark.usefixtures("enable_weekview")
def test_phase1_days_payload_includes_menu_alt2_and_residents(client_admin):
    year, week = 2025, 45
    dep_id = str(uuid.uuid4())
    site_id = str(uuid.uuid4())
    base = f"/api/weekview?year={year}&week={week}&department_id={dep_id}"
    # Align session site context
    with client_admin.session_transaction() as sess:
        sess["site_id"] = site_id

    # Initial GET -> ETag + baseline payload
    r0 = _get(client_admin, "admin", base)
    assert r0.status_code == 200
    etag0 = r0.headers.get("ETag")
    assert etag0 and ETAG_RE.match(etag0)
    data0 = r0.get_json()
    assert isinstance(data0, dict)
    ds0 = data0.get("department_summaries") or []
    assert isinstance(ds0, list) and len(ds0) == 1
    days0 = ds0[0].get("days") or []
    assert isinstance(days0, list) and len(days0) == 7

    # Seed menu variants for Monday lunch (alt1 + alt2)
    app = client_admin.application
    with app.app_context():
        # Ensure ORM tables present in ephemeral sqlite
        from core.db import create_all, get_session
        from core.models import Dish

        create_all()
        db = get_session()
        try:
            d1 = Dish(tenant_id=1, name="Köttbullar", category=None)
            d2 = Dish(tenant_id=1, name="Fiskgratäng", category=None)
            db.add_all([d1, d2])
            db.commit()
            db.refresh(d1)
            db.refresh(d2)
        finally:
            db.close()
        menu = app.menu_service.create_or_get_menu(tenant_id=1, week=week, year=year)
        app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt1", dish_id=d1.id)
        app.menu_service.set_variant(tenant_id=1, menu_id=menu.id, day="mon", meal="lunch", variant_type="alt2", dish_id=d2.id)

    # Set Alt2 flag for Monday and residents count for Monday lunch
    r_alt2 = _patch(
        client_admin,
        "editor",
        "/api/weekview/alt2",
        json={
            "tenant_id": 1,
            "site_id": site_id,
            "department_id": dep_id,
            "year": year,
            "week": week,
            "days": [1],
        },
        extra_headers={"If-Match": etag0},
    )
    assert r_alt2.status_code in (200, 201)
    etag1 = r_alt2.headers.get("ETag") or etag0

    r_res = _patch(
        client_admin,
        "admin",
        "/api/weekview/residents",
        json={
            "tenant_id": 1,
            "site_id": site_id,
            "department_id": dep_id,
            "year": year,
            "week": week,
            "items": [{"day_of_week": 1, "meal": "lunch", "count": 12}],
        },
        extra_headers={"If-Match": etag1},
    )
    assert r_res.status_code in (200, 201)

    # GET again -> verify days[0] carries menu_texts + alt2_lunch + residents
    r1 = _get(client_admin, "viewer", base)
    assert r1.status_code == 200
    assert ETAG_RE.match(r1.headers.get("ETag") or "")
    data1 = r1.get_json()
    ds1 = data1.get("department_summaries") or []
    days1 = ds1[0].get("days") or []
    assert len(days1) == 7
    mon = days1[0]
    assert mon.get("day_of_week") == 1
    assert mon.get("date")
    assert mon.get("weekday_name") in ("Mon", "Mån", "Monday")
    mt = mon.get("menu_texts") or {}
    assert mt.get("lunch", {}).get("alt1") == "Köttbullar"
    assert mt.get("lunch", {}).get("alt2") == "Fiskgratäng"
    assert mon.get("alt2_lunch") is True
    assert mon.get("residents", {}).get("lunch") == 12

    # Backwards-compat fields still present
    assert isinstance(ds1[0].get("marks"), list)
    assert isinstance(ds1[0].get("residents_counts"), list)
    assert isinstance(ds1[0].get("alt2_days"), list)

    # Conditional GET (If-None-Match)
    r_not_mod = client_admin.get(base, headers={"X-User-Role": "viewer", "X-Tenant-Id": "1", "If-None-Match": r1.headers.get("ETag")})
    assert r_not_mod.status_code in (200, 304)
