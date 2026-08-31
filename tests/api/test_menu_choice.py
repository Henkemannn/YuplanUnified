from __future__ import annotations

from datetime import date as _date
import uuid

from core.db import get_session
from core.admin_repo import SitesRepo, DepartmentsRepo
from core.department_menu_choice_repo import MenuChoiceRepo
from portal.department.auth import DepartmentPortalScope
from portal.department.service import build_department_week_payload
from sqlalchemy import text

WEEK = 47
CURRENT_YEAR = int(_date.today().isocalendar()[0])
NEXT_YEAR = CURRENT_YEAR + 1
DEPT_ID = "77777777-1111-2222-3333-999999999999"


def _auth_headers(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _set_auth_session(client, *, tenant_id: int = 1, user_id: int = 1, role: str = "admin", site_id: str | None = None) -> None:
    with client.session_transaction() as sess:
        sess["tenant_id"] = tenant_id
        sess["user_id"] = user_id
        sess["role"] = role
        if site_id is not None:
            sess["site_id"] = site_id


def _ensure_department(client):
    if getattr(client, "_mc_dept", None):
        return getattr(client, "_mc_dept")
    suffix = uuid.uuid4().hex[:8]
    site_repo = SitesRepo()
    dept_repo = DepartmentsRepo()
    site, _ = site_repo.create_site(f"MC-Site-{suffix}", tenant_id=1)
    dep, _ = dept_repo.create_department(
        site_id=site["id"],
        name=f"MC-Dept-{suffix}",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    site_id = site["id"]
    dep_id = dep["id"]
    setattr(client, "_mc_dept", dep_id)
    setattr(client, "_mc_site", site_id)
    return dep_id


def _seed_legacy_alt2(db, *, site_id: str, department_id: str, year: int, week: int, weekday: int, enabled: int = 1) -> None:
    db.execute(
        text("DELETE FROM alt2_flags WHERE site_id=:s AND department_id=:d AND week=:w AND weekday=:dow"),
        {"s": site_id, "d": department_id, "w": week, "dow": weekday},
    )
    db.execute(
        text(
            "INSERT OR REPLACE INTO alt2_flags(site_id,department_id,week,weekday,enabled,version) VALUES(:s,:d,:w,:dow,:enabled,1)"
        ),
        {"s": site_id, "d": department_id, "w": week, "dow": weekday, "enabled": enabled},
    )
    db.commit()


def _seed_basic(client) -> tuple[str, str]:
    dep_id = _ensure_department(client)
    site_id = getattr(client, "_mc_site", None)
    assert site_id
    db = get_session()
    try:
        db.execute(text("DELETE FROM alt2_flags WHERE site_id=:s AND department_id=:d"), {"s": site_id, "d": dep_id})
        db.execute(text("DELETE FROM department_menu_choices WHERE site_id=:s AND department_id=:d"), {"s": site_id, "d": dep_id})
        db.commit()
    finally:
        db.close()
    _set_auth_session(client, site_id=site_id)
    return dep_id, site_id


def _admin_get(client, dep_id: str, year: int | None = None):
    year_q = f"&year={year}" if year is not None else ""
    r = client.get(f"/menu-choice?week={WEEK}&department={dep_id}{year_q}", headers=_auth_headers("editor"))
    assert r.status_code == 200
    return r


def _admin_put(client, dep_id: str, etag: str, day: str, choice: str):
    return client.put(
        "/menu-choice",
        headers={**_auth_headers("editor"), "If-Match": etag},
        json={"week": WEEK, "department": dep_id, "day": day, "choice": choice},
    )


class TestMenuChoiceAPI:
    def test_get_returns_none_when_unselected_and_ignores_legacy_alt2(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        db = get_session()
        try:
            _seed_legacy_alt2(db, site_id=site_id, department_id=dep_id, year=CURRENT_YEAR, week=WEEK, weekday=1)
        finally:
            db.close()

        r = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        etag = r.headers.get("ETag")
        assert etag and etag.startswith(f'W/"admin:menu-choice:{dep_id}:{CURRENT_YEAR}:{WEEK}:')
        body = r.get_json()
        assert body["week"] == WEEK
        assert body["department"] == dep_id
        assert set(body["days"].keys()) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        assert all(v is None for v in body["days"].values())

    def test_get_without_tenant_header_uses_authenticated_session(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        _set_auth_session(client_admin, tenant_id=1, user_id=1, role="admin", site_id=site_id)

        r = client_admin.get(f"/menu-choice?week={WEEK}&year={CURRENT_YEAR}&department={dep_id}")
        assert r.status_code == 200
        assert r.get_json()["department"] == dep_id

    def test_conflicting_tenant_header_does_not_override_authenticated_session(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        _set_auth_session(client_admin, tenant_id=1, user_id=1, role="admin", site_id=site_id)

        app = client_admin.application
        original_before = {k: list(v) for k, v in app.before_request_funcs.items()}
        try:
            app.before_request_funcs[None] = []
            r = client_admin.get(
                f"/menu-choice?week={WEEK}&year={CURRENT_YEAR}&department={dep_id}",
                headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
            )
            assert r.status_code == 200
            assert r.get_json()["department"] == dep_id
        finally:
            app.before_request_funcs = original_before

    def test_get_returns_explicit_alt2_from_canonical_choice(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=CURRENT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt2",
        )

        r = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        body = r.get_json()
        assert body["days"]["mon"] == "Alt2"
        assert body["days"]["tue"] is None

    def test_get_returns_explicit_alt1_from_canonical_choice(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=CURRENT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt1",
        )

        r = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        body = r.get_json()
        assert body["days"]["mon"] == "Alt1"
        assert body["days"]["tue"] is None

    def test_get_explicit_year_separates_years(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=CURRENT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt1",
        )
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=NEXT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt2",
        )

        body_2026 = _admin_get(client_admin, dep_id, CURRENT_YEAR).get_json()
        body_2027 = _admin_get(client_admin, dep_id, NEXT_YEAR).get_json()
        assert body_2026["days"]["mon"] == "Alt1"
        assert body_2027["days"]["mon"] == "Alt2"

    def test_department_from_other_tenant_is_rejected(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        db = get_session()
        try:
            db.execute(text("INSERT OR REPLACE INTO tenants(id, name, active) VALUES(2, 'OtherTenant', 1)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id, name, tenant_id, version) VALUES('other-site', 'OtherSite', 2, 0)"))
            db.execute(
                text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode) VALUES('other-dept', 'other-site', 'OtherDept', 'manual')")
            )
            db.commit()
        finally:
            db.close()

        _set_auth_session(client_admin, tenant_id=1, user_id=1, role="admin", site_id=site_id)
        r = client_admin.get("/menu-choice?week=47&year=%s&department=other-dept" % CURRENT_YEAR)
        assert r.status_code == 400
        body = r.get_json() or {}
        assert body.get("message") == "department_not_found" or body.get("detail") == "department_not_found" or body.get("error") == "department_not_found"

    def test_unknown_department_returns_controlled_4xx(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        _set_auth_session(client_admin, tenant_id=1, user_id=1, role="admin", site_id=site_id)

        r = client_admin.get("/menu-choice?week=47&year=%s&department=missing-dept" % CURRENT_YEAR)
        assert r.status_code == 400
        body = r.get_json() or {}
        assert body.get("message") == "department_not_found" or body.get("detail") == "department_not_found" or body.get("error") == "department_not_found"

    def test_put_requires_if_match(self, client_admin):
        dep_id, _site_id = _seed_basic(client_admin)
        r = client_admin.put(
            "/menu-choice",
            headers=_auth_headers("editor"),
            json={"week": WEEK, "department": dep_id, "day": "tue", "choice": "Alt1"},
        )
        assert r.status_code == 412

    def test_put_alt2_writes_canonical_and_mirrors_legacy(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        r0 = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        et0 = r0.headers.get("ETag")
        assert et0

        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"year": CURRENT_YEAR, "week": WEEK, "department": dep_id, "day": "mon", "choice": "Alt2"},
        )
        assert r_put.status_code == 204
        et_after_put = r_put.headers.get("ETag")
        assert et_after_put and et_after_put != et0

        r1 = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        body = r1.get_json()
        assert body["days"]["mon"] == "Alt2"

        db = get_session()
        try:
            row = db.execute(
                text(
                    "SELECT selected_variant FROM department_menu_choices WHERE tenant_id=1 AND site_id=:s AND department_id=:d AND year=:y AND week=:w AND weekday=1 AND meal='lunch'"
                ),
                {"s": site_id, "d": dep_id, "y": CURRENT_YEAR, "w": WEEK},
            ).fetchone()
            assert row and str(row[0]) == "alt2"
            legacy = db.execute(
                text("SELECT enabled FROM alt2_flags WHERE site_id=:s AND department_id=:d AND week=:w AND weekday=1"),
                {"s": site_id, "d": dep_id, "w": WEEK},
            ).fetchone()
            assert legacy and int(legacy[0]) == 1
        finally:
            db.close()

        scope = DepartmentPortalScope(user_id=1, role="admin", tenant_id=1, department_id=dep_id, site_id=site_id)
        payload = build_department_week_payload(scope, CURRENT_YEAR, WEEK)
        monday = next(d for d in payload["days"] if d["weekday_name"] == "Måndag")
        assert monday["choice"]["selected_alt"] == "Alt2"

    def test_put_alt2_current_year_updates_legacy_mirror_only_for_current_year(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=CURRENT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt1",
        )
        r0 = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        et0 = r0.headers.get("ETag")
        assert et0

        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"year": CURRENT_YEAR, "week": WEEK, "department": dep_id, "day": "mon", "choice": "Alt2"},
        )
        assert r_put.status_code == 204

        db = get_session()
        try:
            row = db.execute(
                text("SELECT selected_variant FROM department_menu_choices WHERE tenant_id=1 AND site_id=:s AND department_id=:d AND year=:y AND week=:w AND weekday=1 AND meal='lunch'"),
                {"s": site_id, "d": dep_id, "y": CURRENT_YEAR, "w": WEEK},
            ).fetchone()
            assert row and str(row[0]) == "alt2"
            legacy = db.execute(
                text("SELECT enabled FROM alt2_flags WHERE site_id=:s AND department_id=:d AND week=:w AND weekday=1"),
                {"s": site_id, "d": dep_id, "w": WEEK},
            ).fetchone()
            assert legacy and int(legacy[0]) == 1
        finally:
            db.close()

    def test_put_future_year_alt2_does_not_touch_legacy_mirror(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        db = get_session()
        try:
            _seed_legacy_alt2(db, site_id=site_id, department_id=dep_id, year=CURRENT_YEAR, week=WEEK, weekday=1, enabled=1)
        finally:
            db.close()
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=NEXT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt1",
        )
        r0 = _admin_get(client_admin, dep_id, NEXT_YEAR)
        et0 = r0.headers.get("ETag")
        assert et0
        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"year": NEXT_YEAR, "week": WEEK, "department": dep_id, "day": "mon", "choice": "Alt2"},
        )
        assert r_put.status_code == 204
        db = get_session()
        try:
            legacy = db.execute(
                text("SELECT enabled FROM alt2_flags WHERE site_id=:s AND department_id=:d AND week=:w AND weekday=1"),
                {"s": site_id, "d": dep_id, "w": WEEK},
            ).fetchone()
            assert legacy and int(legacy[0]) == 1
        finally:
            db.close()

    def test_put_future_year_alt1_does_not_touch_legacy_mirror(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        db = get_session()
        try:
            _seed_legacy_alt2(db, site_id=site_id, department_id=dep_id, year=CURRENT_YEAR, week=WEEK, weekday=1, enabled=1)
        finally:
            db.close()
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=NEXT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt2",
        )
        r0 = _admin_get(client_admin, dep_id, NEXT_YEAR)
        et0 = r0.headers.get("ETag")
        assert et0
        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"year": NEXT_YEAR, "week": WEEK, "department": dep_id, "day": "mon", "choice": "Alt1"},
        )
        assert r_put.status_code == 204
        db = get_session()
        try:
            legacy = db.execute(
                text("SELECT enabled FROM alt2_flags WHERE site_id=:s AND department_id=:d AND week=:w AND weekday=1"),
                {"s": site_id, "d": dep_id, "w": WEEK},
            ).fetchone()
            assert legacy and int(legacy[0]) == 1
        finally:
            db.close()

    def test_cross_year_etags_differ_and_cannot_be_reused(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=CURRENT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt1",
        )
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=NEXT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt1",
        )
        et_current = _admin_get(client_admin, dep_id, CURRENT_YEAR).headers.get("ETag")
        et_next = _admin_get(client_admin, dep_id, NEXT_YEAR).headers.get("ETag")
        assert et_current and et_next and et_current != et_next

        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et_current},
            json={"year": NEXT_YEAR, "week": WEEK, "department": dep_id, "day": "mon", "choice": "Alt2"},
        )
        assert r_put.status_code == 412

    def test_put_alt2_explicit_year_targets_only_that_year(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=CURRENT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt1",
        )
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=NEXT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt1",
        )

        r0 = _admin_get(client_admin, dep_id, NEXT_YEAR)
        et0 = r0.headers.get("ETag")
        assert et0

        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"year": NEXT_YEAR, "week": WEEK, "department": dep_id, "day": "mon", "choice": "Alt2"},
        )
        assert r_put.status_code == 204

        body_current = _admin_get(client_admin, dep_id, CURRENT_YEAR).get_json()
        body_next = _admin_get(client_admin, dep_id, NEXT_YEAR).get_json()
        assert body_current["days"]["mon"] == "Alt1"
        assert body_next["days"]["mon"] == "Alt2"

    def test_get_missing_year_defaults_to_current_year(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=CURRENT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt2",
        )
        body_with_year = _admin_get(client_admin, dep_id, CURRENT_YEAR).get_json()
        body_without_year = _admin_get(client_admin, dep_id).get_json()
        assert body_with_year["days"]["mon"] == "Alt2"
        assert body_without_year["days"]["mon"] == "Alt2"

    def test_put_alt1_writes_canonical_and_clears_legacy(self, client_admin):
        dep_id, site_id = _seed_basic(client_admin)
        repo = MenuChoiceRepo()
        repo.set_choice(
            tenant_id=1,
            site_id=site_id,
            department_id=dep_id,
            year=CURRENT_YEAR,
            week=WEEK,
            weekday=1,
            selected_alt="Alt2",
        )
        r0 = _admin_get(client_admin, dep_id)
        et0 = r0.headers.get("ETag")
        assert et0

        r_put = _admin_put(client_admin, dep_id, et0, "mon", "Alt1")
        assert r_put.status_code == 204

        r1 = _admin_get(client_admin, dep_id)
        body = r1.get_json()
        assert body["days"]["mon"] == "Alt1"

        db = get_session()
        try:
            row = db.execute(
                text(
                    "SELECT selected_variant FROM department_menu_choices WHERE tenant_id=1 AND site_id=:s AND department_id=:d AND year=:y AND week=:w AND weekday=1 AND meal='lunch'"
                ),
                {"s": site_id, "d": dep_id, "y": CURRENT_YEAR, "w": WEEK},
            ).fetchone()
            assert row and str(row[0]) == "alt1"
            legacy = db.execute(
                text("SELECT enabled FROM alt2_flags WHERE site_id=:s AND department_id=:d AND week=:w AND weekday=1"),
                {"s": site_id, "d": dep_id, "w": WEEK},
            ).fetchone()
            assert legacy is None
        finally:
            db.close()

        scope = DepartmentPortalScope(user_id=1, role="admin", tenant_id=1, department_id=dep_id, site_id=site_id)
        payload = build_department_week_payload(scope, CURRENT_YEAR, WEEK)
        monday = next(d for d in payload["days"] if d["weekday_name"] == "Måndag")
        assert monday["choice"]["selected_alt"] == "Alt1"

    def test_put_stale_if_match_yields_412(self, client_admin):
        dep_id, _site_id = _seed_basic(client_admin)
        r0a = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        r0b = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        et0 = r0a.headers.get("ETag")
        r_put1 = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"year": CURRENT_YEAR, "week": WEEK, "department": dep_id, "day": "wed", "choice": "Alt2"},
        )
        assert r_put1.status_code == 204
        et_stale = r0b.headers.get("ETag")
        r_put2 = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et_stale},
            json={"year": CURRENT_YEAR, "week": WEEK, "department": dep_id, "day": "thu", "choice": "Alt2"},
        )
        assert r_put2.status_code == 412

    def test_weekend_rule_alt2_is_422_with_problem_details(self, client_admin):
        dep_id, _site_id = _seed_basic(client_admin)
        r0 = _admin_get(client_admin, dep_id, CURRENT_YEAR)
        et0 = r0.headers.get("ETag")
        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"year": CURRENT_YEAR, "week": WEEK, "department": dep_id, "day": "sat", "choice": "Alt2"},
        )
        assert r_put.status_code == 422
        pb = r_put.get_json()
        assert pb["type"].endswith("/menu-choice/alt2-weekend")
        assert pb["title"] == "Alt2 not permitted on weekends"
        assert pb["status"] == 422
        assert pb["detail"]
        assert pb.get("instance") == "/menu-choice"
        assert pb["week"] == WEEK
        assert pb["department"] == dep_id
        assert pb["day"] == "sat"