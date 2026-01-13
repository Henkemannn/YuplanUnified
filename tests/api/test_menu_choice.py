from __future__ import annotations

import pytest

WEEK = 47


def _auth_headers(role: str = "admin"):
    return {"X-User-Role": role, "X-Tenant-Id": "1"}


def _ensure_department(client):
    # Create site + department once; cache ids on client object to reuse between tests
    if getattr(client, "_mc_dept", None):
        return getattr(client, "_mc_dept")
    r_site = client.post(
        "/admin/sites",
        headers=_auth_headers(),
        json={"name": "MC-Site"},
    )
    assert r_site.status_code == 200, r_site.data
    site_id = r_site.get_json()["id"]
    r_dep = client.post(
        "/admin/departments",
        headers=_auth_headers(),
        json={
            "site_id": site_id,
            "name": "MC-Dept",
            "resident_count_mode": "fixed",
            "resident_count_fixed": 10,
        },
    )
    assert r_dep.status_code == 200, r_dep.data
    dep_id = r_dep.get_json()["id"]
    setattr(client, "_mc_dept", dep_id)
    return dep_id


class TestMenuChoiceAPI:
    def test_get_returns_default_alt1_and_etag(self, client_admin):
        dep_id = _ensure_department(client_admin)
        r = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        assert r.status_code == 200
        etag = r.headers.get("ETag")
        assert etag and etag.startswith('W/"admin:menu-choice:')
        body = r.get_json()
        assert body["week"] == WEEK
        assert body["department"] == dep_id
        assert set(body["days"].keys()) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        assert all(v == "Alt1" for v in body["days"].values())

    def test_get_304_when_if_none_match_matches(self, client_admin):
        dep_id = _ensure_department(client_admin)
        r1 = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        assert r1.status_code == 200
        et = r1.headers.get("ETag")
        r2 = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}",
            headers={**_auth_headers("editor"), "If-None-Match": et},
        )
        assert r2.status_code == 304
        assert r2.headers.get("ETag") == et
        assert not r2.data or r2.data == b""

    def test_put_requires_if_match(self, client_admin):
        dep_id = _ensure_department(client_admin)
        r = client_admin.put(
            "/menu-choice",
            headers=_auth_headers("editor"),
            json={"week": WEEK, "department": dep_id, "day": "tue", "choice": "Alt1"},
        )
        assert r.status_code == 412

    def test_put_idempotent_keeps_etag(self, client_admin):
        dep_id = _ensure_department(client_admin)
        r0 = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        et0 = r0.headers.get("ETag")
        assert et0
        # Idempotent: Tue already Alt1 by default
        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"week": WEEK, "department": dep_id, "day": "tue", "choice": "Alt1"},
        )
        assert r_put.status_code == 204
        et_after_put = r_put.headers.get("ETag")
        assert et_after_put == et0
        r1 = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        et1 = r1.headers.get("ETag")
        assert et1 == et0

    def test_put_mutation_bumps_etag(self, client_admin):
        dep_id = _ensure_department(client_admin)
        r0 = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        et0 = r0.headers.get("ETag")
        assert et0
        # Mutation: set Tue to Alt2
        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"week": WEEK, "department": dep_id, "day": "tue", "choice": "Alt2"},
        )
        assert r_put.status_code == 204
        et_after_put = r_put.headers.get("ETag")
        assert et_after_put and et_after_put != et0
        r1 = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        et1 = r1.headers.get("ETag")
        body = r1.get_json()
        assert et1 != et0
        assert body["days"]["tue"] == "Alt2"

    def test_put_stale_if_match_yields_412(self, client_admin):
        dep_id = _ensure_department(client_admin)
        r0a = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        r0b = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        et0 = r0a.headers.get("ETag")
        # K1 mutation
        r_put1 = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"week": WEEK, "department": dep_id, "day": "wed", "choice": "Alt2"},
        )
        assert r_put1.status_code == 204
        # K2 stale
        et_stale = r0b.headers.get("ETag")
        r_put2 = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et_stale},
            json={"week": WEEK, "department": dep_id, "day": "thu", "choice": "Alt2"},
        )
        assert r_put2.status_code == 412

    def test_weekend_rule_alt2_is_422_with_problem_details(self, client_admin):
        dep_id = _ensure_department(client_admin)
        # Ensure we have an up-to-date etag
        r0 = client_admin.get(
            f"/menu-choice?week={WEEK}&department={dep_id}", headers=_auth_headers("editor")
        )
        et0 = r0.headers.get("ETag")
        # Try to set sat Alt2
        r_put = client_admin.put(
            "/menu-choice",
            headers={**_auth_headers("editor"), "If-Match": et0},
            json={"week": WEEK, "department": dep_id, "day": "sat", "choice": "Alt2"},
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
