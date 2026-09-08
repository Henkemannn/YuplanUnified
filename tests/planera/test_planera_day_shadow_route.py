from __future__ import annotations

from datetime import date

import pytest

from core.admin_repo import DepartmentsRepo, SitesRepo
from core.db import create_all, get_session
from core.models import TenantFeatureFlag
from sqlalchemy import text


def _h(role: str = "admin") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _enable_planera_api(app) -> None:
    with app.app_context():
        reg = getattr(app, "feature_registry", None)
        if reg:
            if not reg.has("ff.planera.enabled"):
                reg.add("ff.planera.enabled")
            reg.set("ff.planera.enabled", True)


def _seed_site_and_department(app, *, site_name: str = "PlaneraSite") -> tuple[str, str]:
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(1, 'Tenant 1', 1)"))
            db.commit()
        finally:
            db.close()
        site, _ = SitesRepo().create_site(name=site_name, tenant_id=1)
        department, _ = DepartmentsRepo().create_department(
            site_id=site["id"],
            name="Avd P",
            resident_count_mode="fixed",
            resident_count_fixed=0,
        )
    return site["id"], department["id"]


def _seed_owned_sites_and_departments(app) -> tuple[tuple[str, str], tuple[str, str]]:
    with app.app_context():
        create_all()
        db = get_session()
        try:
            db.execute(text("INSERT OR IGNORE INTO tenants(id, name, active) VALUES(1, 'Tenant 1', 1)"))
            db.commit()
        finally:
            db.close()
        site_a, _ = SitesRepo().create_site(name="Site A", tenant_id=1)
        dep_a, _ = DepartmentsRepo().create_department(
            site_id=site_a["id"],
            name="Avd A",
            resident_count_mode="fixed",
            resident_count_fixed=0,
        )
        site_b, _ = SitesRepo().create_site(name="Site B", tenant_id=1)
        dep_b, _ = DepartmentsRepo().create_department(
            site_id=site_b["id"],
            name="Avd B",
            resident_count_mode="fixed",
            resident_count_fixed=0,
        )
    return (site_a["id"], dep_a["id"]), (site_b["id"], dep_b["id"])


def _set_tenant_shadow_flag(app, *, enabled: bool | None) -> None:
    with app.app_context():
        db = get_session()
        try:
            db.query(TenantFeatureFlag).filter_by(tenant_id=1, name="ff.planera2.shadow").delete()
            if enabled is not None:
                db.add(TenantFeatureFlag(tenant_id=1, name="ff.planera2.shadow", enabled=enabled))
            db.commit()
        finally:
            db.close()


def _route_payload(site_id: str, site_name: str, d: str, dep_id: str) -> dict[str, object]:
    return {
        "site_id": site_id,
        "site_name": site_name,
        "date": d,
        "meal_labels": {"lunch": "Lunch", "dinner": "Kvällsmat"},
        "departments": [
            {
                "department_id": dep_id,
                "department_name": "Avd P",
                "meals": {
                    "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
                    "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
                },
            }
        ],
        "totals": {
            "lunch": {"residents_total": 10, "special_diets": [], "normal_diet_count": 10},
            "dinner": {"residents_total": 8, "special_diets": [], "normal_diet_count": 8},
        },
    }


@pytest.mark.parametrize(
    ("shadow_flag_value", "expected_mode"),
    [
        (None, "legacy"),
        (False, "legacy"),
        (True, "shadow"),
    ],
)
def test_planera_day_shadow_flag_controls_application_mode(client_admin, monkeypatch: pytest.MonkeyPatch, shadow_flag_value, expected_mode):
    app = client_admin.application
    site_id, dep_id = _seed_site_and_department(app, site_name="PlaneraSite")
    d = date(2025, 11, 20).isoformat()
    _enable_planera_api(app)
    _set_tenant_shadow_flag(app, enabled=shadow_flag_value)

    observed: list[dict[str, object]] = []

    def _run_application(**kwargs: object) -> dict[str, object]:
        observed.append(dict(kwargs))
        return _route_payload(site_id, "Resolved Site", d, dep_id)

    monkeypatch.setattr("core.planera_api.run_kommun_day_application", _run_application)

    rv = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))

    assert rv.status_code == 200
    assert rv.get_json() == _route_payload(site_id, "Resolved Site", d, dep_id)
    assert observed == [
        {
            "mode": expected_mode,
            "tenant_id": 1,
            "site_id": site_id,
            "service_date": d,
            "meal_labels": {"lunch": "Lunch", "dinner": "Kvällsmat"},
            "department_id": dep_id,
        }
    ]


def test_planera_day_shadow_and_legacy_response_are_identical_for_same_payload(client_admin, monkeypatch: pytest.MonkeyPatch):
    app = client_admin.application
    site_id, dep_id = _seed_site_and_department(app, site_name="PlaneraSite")
    d = date(2025, 11, 20).isoformat()
    _enable_planera_api(app)

    def _run_application(**kwargs: object) -> dict[str, object]:
        return _route_payload(site_id, "Resolved Site", d, dep_id)

    monkeypatch.setattr("core.planera_api.run_kommun_day_application", _run_application)

    _set_tenant_shadow_flag(app, enabled=False)
    legacy = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))

    _set_tenant_shadow_flag(app, enabled=True)
    shadow = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))

    assert legacy.status_code == 200
    assert shadow.status_code == 200
    assert legacy.get_json() == shadow.get_json() == _route_payload(site_id, "Resolved Site", d, dep_id)
    assert legacy.headers["ETag"] == shadow.headers["ETag"]
    assert legacy.headers["Cache-Control"] == "private, max-age=0, must-revalidate"
    assert shadow.headers["Cache-Control"] == "private, max-age=0, must-revalidate"


@pytest.mark.parametrize("resolver_code", ["site_not_owned", "site_not_found", "department_scope_mismatch"])
def test_planera_day_resolver_errors_map_to_existing_404_shape(client_admin, monkeypatch: pytest.MonkeyPatch, resolver_code: str):
    app = client_admin.application
    site_id, dep_id = _seed_site_and_department(app, site_name="PlaneraSite")
    d = date(2025, 11, 20).isoformat()
    _enable_planera_api(app)
    _set_tenant_shadow_flag(app, enabled=True)

    from core.planera_v2.day_context_resolver import KommunDayContextResolverError

    def _boom(**kwargs: object) -> dict[str, object]:
        raise KommunDayContextResolverError(resolver_code, resolver_code)

    monkeypatch.setattr("core.planera_api.run_kommun_day_application", _boom)

    rv = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))

    assert rv.status_code == 404
    body = rv.get_json()
    assert body["detail"] == "site_or_department_not_found"
    assert rv.mimetype == "application/problem+json"


def test_planera_day_route_does_not_call_planera_service_compute_day(client_admin, monkeypatch: pytest.MonkeyPatch):
    app = client_admin.application
    site_id, dep_id = _seed_site_and_department(app, site_name="PlaneraSite")
    d = date(2025, 11, 20).isoformat()
    _enable_planera_api(app)
    _set_tenant_shadow_flag(app, enabled=False)

    from core import planera_service as planera_service_module

    def _boom(*args: object, **kwargs: object) -> dict[str, object]:
        return _route_payload(site_id, "Resolved Site", d, dep_id)

    def _should_not_run(*args: object, **kwargs: object):
        raise AssertionError("route must not call PlaneraService.compute_day directly")

    monkeypatch.setattr("core.planera_api.run_kommun_day_application", _boom)
    monkeypatch.setattr(planera_service_module.PlaneraService, "compute_day", _should_not_run)

    rv = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))

    assert rv.status_code == 200
    assert rv.get_json() == _route_payload(site_id, "Resolved Site", d, dep_id)


def test_planera_day_wrong_tenant_returns_existing_404_shape(client_admin):
    app = client_admin.application
    (site_id, dep_id), _ = _seed_owned_sites_and_departments(app)
    d = date(2025, 11, 20).isoformat()
    _enable_planera_api(app)
    _set_tenant_shadow_flag(app, enabled=None)

    rv = client_admin.get(
        f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )

    assert rv.status_code == 404
    body = rv.get_json()
    assert body["detail"] == "site_or_department_not_found"
    assert rv.mimetype == "application/problem+json"


def test_planera_day_wrong_department_scope_returns_existing_404_shape(client_admin):
    app = client_admin.application
    (site_a_id, _dep_a_id), (_site_b_id, dep_b_id) = _seed_owned_sites_and_departments(app)
    d = date(2025, 11, 20).isoformat()
    _enable_planera_api(app)
    _set_tenant_shadow_flag(app, enabled=None)

    rv = client_admin.get(
        f"/api/planera/day?site_id={site_a_id}&date={d}&department_id={dep_b_id}",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "1"},
    )

    assert rv.status_code == 404
    body = rv.get_json()
    assert body["detail"] == "site_or_department_not_found"
    assert rv.mimetype == "application/problem+json"


def test_planera_day_shadow_flag_false_is_legacy_and_etag_304_still_works(client_admin, monkeypatch: pytest.MonkeyPatch):
    app = client_admin.application
    site_id, dep_id = _seed_site_and_department(app, site_name="PlaneraSite")
    d = date(2025, 11, 20).isoformat()
    _enable_planera_api(app)
    _set_tenant_shadow_flag(app, enabled=False)

    def _run_application(**kwargs: object) -> dict[str, object]:
        return _route_payload(site_id, "Resolved Site", d, dep_id)

    monkeypatch.setattr("core.planera_api.run_kommun_day_application", _run_application)

    first = client_admin.get(f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}", headers=_h("admin"))
    etag = first.headers["ETag"]
    second = client_admin.get(
        f"/api/planera/day?site_id={site_id}&date={d}&department_id={dep_id}",
        headers={**_h("admin"), "If-None-Match": etag},
    )

    assert first.status_code == 200
    assert first.get_json() == _route_payload(site_id, "Resolved Site", d, dep_id)
    assert second.status_code == 304
    assert second.get_data(as_text=True) == ""
    assert second.headers["ETag"] == etag
    assert first.headers["Cache-Control"] == "private, max-age=0, must-revalidate"
    assert second.headers["Cache-Control"] == "private, max-age=0, must-revalidate"
