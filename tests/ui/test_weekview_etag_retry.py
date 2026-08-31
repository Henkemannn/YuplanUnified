from __future__ import annotations

import os
from datetime import date as _date
import uuid

from flask.testing import FlaskClient

from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo
from core.department_menu_choice_repo import MenuChoiceRepo
from core.weekview.service import WeekviewService
from core.weekview.repo import WeekviewRepo


def _login_headers(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def seed_basic():
    srepo = SitesRepo()
    suffix = uuid.uuid4().hex[:8]
    site, _ = srepo.create_site(f"TestSite-{suffix}")
    drepo = DepartmentsRepo()
    dep, _ = drepo.create_department(site_id=site["id"], name=f"Avd A {suffix}", resident_count_mode="fixed", resident_count_fixed=10)
    trepo = DietTypesRepo()
    dt_id = trepo.create(tenant_id=1, name=f"Glutenfri {suffix}", default_select=False)
    drepo.upsert_department_diet_defaults(dep["id"], 0, [{"diet_type_id": str(dt_id), "default_count": 2}])
    return site, dep, dt_id


def test_etag_stale_then_retry_with_fresh_etag(app_session):
    os.environ["STRICT_CSRF_IN_TESTS"] = "0"
    app = app_session
    client: FlaskClient = app.test_client()
    if not app.feature_registry.has("ff.weekview.enabled"):
        app.feature_registry.add("ff.weekview.enabled")
    app.feature_registry.set("ff.weekview.enabled", True)
    site, dep, dt_id = seed_basic()
    # Align session site context for mutations
    client.post(
        "/ui/select-site",
        data={"site_id": site["id"], "next": "/"},
        headers=_login_headers(),
    )

    iso = _date.today().isocalendar()
    year, week = iso[0], iso[1]

    svc = WeekviewService()
    repo = WeekviewRepo()
    _ = repo.get_version(tenant_id=1, year=year, week=week, department_id=dep["id"])  # seed version=0
    etag_v0 = svc.build_etag(tenant_id=1, department_id=dep["id"], year=year, week=week, version=0)

    # Live GET and helper ETag should initially agree.
    r0 = client.get(f"/api/weekview?department_id={dep['id']}&year={year}&week={week}", headers=_login_headers())
    assert r0.status_code == 200
    assert r0.headers.get("ETag") == etag_v0
    r0_helper = client.get(f"/api/weekview/etag?department_id={dep['id']}&year={year}&week={week}", headers=_login_headers())
    assert r0_helper.status_code == 200
    assert r0_helper.get_json()["etag"] == etag_v0

    # Canonical explicit choice must change the effective ETag even if weekview_versions stays the same.
    choice_repo = MenuChoiceRepo()
    choice_repo.set_choice(
        tenant_id=1,
        site_id=site["id"],
        department_id=dep["id"],
        year=year,
        week=week,
        weekday=1,
        selected_alt="Alt2",
    )
    assert repo.get_version(tenant_id=1, year=year, week=week, department_id=dep["id"]) == 0

    r1 = client.get(f"/api/weekview/etag?department_id={dep['id']}&year={year}&week={week}", headers=_login_headers())
    assert r1.status_code == 200
    etag_choice = r1.get_json()["etag"]
    assert etag_choice and etag_choice != etag_v0

    r1_live = client.get(
        f"/api/weekview?department_id={dep['id']}&year={year}&week={week}",
        headers={**_login_headers(), "If-None-Match": etag_v0},
    )
    assert r1_live.status_code == 200
    assert r1_live.headers.get("ETag") == etag_choice

    r1_304 = client.get(
        f"/api/weekview?department_id={dep['id']}&year={year}&week={week}",
        headers={**_login_headers(), "If-None-Match": etag_choice},
    )
    assert r1_304.status_code == 304

    payload = {
        "year": year,
        "week": week,
        "department_id": dep["id"],
        "diet_type_id": str(dt_id),
        "meal": "Lunch",
        "weekday_abbr": "Mån",
        "marked": True,
    }

    # Stale canonical-aware ETag must fail once the canonical menu choice changes.
    stale_resp = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**_login_headers(), "If-Match": etag_v0})
    assert stale_resp.status_code == 412

    # Retry with the current canonical-aware ETag must succeed.
    r2 = client.get(f"/api/weekview/etag?department_id={dep['id']}&year={year}&week={week}", headers=_login_headers())
    assert r2.status_code == 200
    etag_new = r2.get_json()["etag"]
    assert etag_new and etag_new == etag_choice

    fresh_resp = client.post("/api/weekview/specialdiets/mark", json=payload, headers={**_login_headers(), "If-Match": etag_new})
    assert fresh_resp.status_code == 200
    assert fresh_resp.headers.get("ETag")
    assert fresh_resp.headers.get("ETag") != etag_new
