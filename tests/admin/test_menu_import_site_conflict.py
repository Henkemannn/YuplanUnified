from __future__ import annotations

from io import BytesIO

from sqlalchemy import text

from core.db import get_session


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _client_for_site(app_session, site_id: str):
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR IGNORE INTO users "
                "(id, tenant_id, username, email, password_hash, role, is_active) "
                "VALUES (1, 1, 'menu-import-admin', 'menu-import-admin@example.test', "
                "'not-used', 'admin', 1)"
            )
        )
        db.execute(
            text(
                "UPDATE users SET tenant_id=1, role='admin', is_active=1 "
                "WHERE id=1"
            )
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
                "VALUES (:id, :name, 1, 0)"
            ),
            {"id": site_id, "name": site_id},
        )
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites ("
                "user_id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL)"
            )
        )
        db.execute(
            text(
                "INSERT INTO kitchen_user_sites (user_id, tenant_id, site_id) "
                "VALUES (1, 1, :site_id) "
                "ON CONFLICT(user_id) DO UPDATE SET tenant_id=1, site_id=:site_id"
            ),
            {"site_id": site_id},
        )
        db.commit()
    finally:
        db.close()
    client = app_session.test_client()
    with client.session_transaction() as session:
        session["tenant_id"] = 1
        session["site_id"] = site_id
        session["role"] = "admin"
    return client


def _form(action: str, week: int) -> dict[str, str | list[str]]:
    return {
        "year": "2041",
        "week": str(week),
        "action": action,
        "menu_name": "04K test",
        "row_count": "1",
        "selected_days": ["monday"],
        "row_labels": ["Dagens"],
    }


def test_null_site_menu_is_not_presented_or_reused_by_replace(app_session):
    client = _client_for_site(app_session, "04k-site-a")
    db = get_session()
    try:
        null_menu_id = db.execute(
            text(
                "INSERT INTO menus(tenant_id, site_id, week, year, status) "
                "VALUES (1, NULL, 21, 2041, 'published') RETURNING id"
            )
        ).scalar_one()
        db.commit()
    finally:
        db.close()

    preview = client.post(
        "/ui/admin/menu-import/new",
        data=_form("preview", 21),
        headers=ADMIN_HEADERS,
    )
    assert preview.status_code == 200
    assert preview.get_json()["status"] == "ready"

    open_existing = client.post(
        "/ui/admin/menu-import/new",
        data=_form("open-existing", 21),
        headers=ADMIN_HEADERS,
    )
    assert open_existing.status_code == 404

    replace = client.post(
        "/ui/admin/menu-import/new",
        data=_form("replace", 21),
        headers={**ADMIN_HEADERS, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    assert replace.status_code == 200

    db = get_session()
    try:
        assert db.execute(
            text("SELECT site_id, status FROM menus WHERE id=:id"),
            {"id": null_menu_id},
        ).one() == (None, "published")
        assert db.execute(
            text(
                "SELECT COUNT(*) FROM menus "
                "WHERE tenant_id=1 AND site_id='04k-site-a' AND week=21 AND year=2041"
            )
        ).scalar_one() == 1
    finally:
        db.close()


def test_legacy_site_conflict_returns_409_without_mutating_menu(app_session):
    client = _client_for_site(app_session, "04k-site-b")
    db = __import__("core.db", fromlist=["get_session"]).get_session()
    try:
        db.execute(
            text(
                "CREATE UNIQUE INDEX uq_04k_legacy_menu_tenant_week "
                "ON menus(tenant_id, week, year) "
                "WHERE tenant_id=1 AND week=22 AND year=2041"
            )
        )
        db.execute(
            text(
                "INSERT INTO menus(tenant_id, site_id, week, year, status) "
                "VALUES (1, '04k-site-a', 22, 2041, 'published')"
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        response = client.post(
            "/ui/admin/menu-import/new",
            data=_form("replace", 22),
            headers={**ADMIN_HEADERS, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        assert response.status_code == 409
        assert response.get_json()["error"] == "menu_site_conflict"

        db = get_session()
        try:
            assert db.execute(
                text(
                    "SELECT site_id, status FROM menus "
                    "WHERE tenant_id=1 AND week=22 AND year=2041"
                )
            ).one() == ("04k-site-a", "published")
        finally:
            db.close()
    finally:
        db = __import__("core.db", fromlist=["get_session"]).get_session()
        try:
            db.execute(text("DROP INDEX uq_04k_legacy_menu_tenant_week"))
            db.commit()
        finally:
            db.close()


def test_admin_cannot_import_or_view_site_from_another_tenant(app_session):
    client = _client_for_site(app_session, "04k-site-a")
    db = get_session()
    try:
        db.execute(
        text(
            "INSERT OR IGNORE INTO tenants(id, name) "
            "VALUES (2, 'Other tenant')"
        )
        )
        db.execute(
        text(
            "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
            "VALUES ('other-tenant-site', 'Other tenant site', 2, 0)"
        )
        )
        before = {
        "menus": db.execute(text("SELECT COUNT(*) FROM menus")).scalar_one(),
        "sites": db.execute(text("SELECT COUNT(*) FROM sites")).scalar_one(),
        }
        db.commit()
    finally:
        db.close()


    cross_site = "?site_id=other-tenant-site"
    response = client.get("/ui/admin/menu-import" + cross_site, headers=ADMIN_HEADERS)
    assert response.status_code == 403

    response = client.get(
        "/ui/admin/menu-import/week/2041/23" + cross_site,
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 403

    for action in ("preview", "create", "replace", "open-existing"):
        response = client.post(
            "/ui/admin/menu-import/new" + cross_site,
            data=_form(action, 23),
            headers={**ADMIN_HEADERS, "Accept": "application/json"},
        )
        assert response.status_code == 403
        assert response.get_json()["error"] == "site_forbidden"

    response = client.post(
        "/ui/admin/menu-import/upload" + cross_site,
        data={"menu_file": (BytesIO(b"not imported"), "menu.csv")},
        content_type="multipart/form-data",
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "site_forbidden"

    db = get_session()
    try:
        after = {
            "menus": db.execute(text("SELECT COUNT(*) FROM menus")).scalar_one(),
            "sites": db.execute(text("SELECT COUNT(*) FROM sites")).scalar_one(),
        }
        assert after == before
        assert db.execute(
            text("SELECT COUNT(*) FROM menus WHERE tenant_id=2")
        ).scalar_one() == 0
    finally:
        db.close()


def test_admin_cannot_use_another_site_within_same_tenant(app_session):
    site_a = "same-tenant-site-a"
    site_b = "same-tenant-site-b"
    client = _client_for_site(app_session, site_a)
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
                "VALUES (:id, :name, 1, 0)"
            ),
            {"id": site_b, "name": site_b},
        )
        db.execute(
            text(
                "DELETE FROM menu_variants WHERE menu_id IN "
                "(SELECT id FROM menus WHERE site_id IN (:site_a, :site_b))"
            ),
            {"site_a": site_a, "site_b": site_b},
        )
        db.execute(
            text("DELETE FROM menus WHERE site_id IN (:site_a, :site_b)"),
            {"site_a": site_a, "site_b": site_b},
        )
        db.execute(
            text(
                "INSERT INTO menus(id, tenant_id, site_id, week, year, status) "
                "VALUES (7001, 1, :site_a, 30, 2041, 'draft'), "
                "(7002, 1, :site_b, 30, 2041, 'published')"
            ),
            {"site_a": site_a, "site_b": site_b},
        )
        db.execute(
            text(
                "INSERT INTO menu_variants(menu_id, day, meal, variant_type, dish_id) "
                "VALUES (7001, 'Mån', 'Lunch', 'alt1', NULL), "
                "(7002, 'Mån', 'Lunch', 'alt1', NULL)"
            )
        )
        db.commit()
    finally:
        db.close()

    def snapshot_site_b() -> dict[str, int]:
        db = get_session()
        try:
            return {
                "menus": db.execute(
                    text("SELECT COUNT(*) FROM menus WHERE site_id=:site_id"),
                    {"site_id": site_b},
                ).scalar_one(),
                "variants": db.execute(
                    text(
                        "SELECT COUNT(*) FROM menu_variants mv "
                        "JOIN menus m ON m.id=mv.menu_id WHERE m.site_id=:site_id"
                    ),
                    {"site_id": site_b},
                ).scalar_one(),
                "builder_links": db.execute(
                    text(
                        "SELECT COUNT(*) FROM commun_builder_menu_links "
                        "WHERE tenant_id=1 AND site_id=:site_id"
                    ),
                    {"site_id": site_b},
                ).scalar_one(),
                "publication_pins": db.execute(
                    text(
                        "SELECT COUNT(*) FROM commun_builder_publication_pins "
                        "WHERE tenant_id=1 AND site_id=:site_id"
                    ),
                    {"site_id": site_b},
                ).scalar_one(),
                "revisions": db.execute(
                    text(
                        "SELECT COUNT(*) FROM commun_builder_publication_revisions "
                        "WHERE tenant_id=1 AND site_id=:site_id"
                    ),
                    {"site_id": site_b},
                ).scalar_one(),
            }
        finally:
            db.close()

    before = snapshot_site_b()
    cross_site = "?site_id=" + site_b

    assert client.get("/ui/admin/menu-import" + cross_site, headers=ADMIN_HEADERS).status_code == 403
    assert client.get(
        "/ui/admin/menu-import/week/2041/30" + cross_site,
        headers=ADMIN_HEADERS,
    ).status_code == 403

    for action in ("preview", "create", "replace", "open-existing"):
        response = client.post(
            "/ui/admin/menu-import/new" + cross_site,
            data=_form(action, 31),
            headers={**ADMIN_HEADERS, "Accept": "application/json"},
        )
        assert response.status_code == 403
        assert response.get_json()["error"] == "site_forbidden"

    upload = client.post(
        "/ui/admin/menu-import/upload" + cross_site,
        data={"menu_file": (BytesIO(b"not imported"), "menu.csv")},
        content_type="multipart/form-data",
        headers=ADMIN_HEADERS,
    )
    assert upload.status_code == 403
    assert upload.get_json()["error"] == "site_forbidden"
    assert snapshot_site_b() == before

    same_site_list = client.get("/ui/admin/menu-import", headers=ADMIN_HEADERS)
    assert same_site_list.status_code == 200
    same_site_preview = client.post(
        "/ui/admin/menu-import/new",
        data=_form("preview", 31),
        headers=ADMIN_HEADERS,
    )
    assert same_site_preview.status_code == 200
    assert same_site_preview.get_json()["status"] == "ready"


def test_admin_cannot_publish_or_unpublish_another_site_menu(app_session):
    site_a = "publication-site-a"
    site_b = "publication-site-b"
    client = _client_for_site(app_session, site_a)
    db = get_session()
    try:
        db.execute(
            text(
                "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
                "VALUES (:id, :name, 1, 0)"
            ),
            {"id": site_b, "name": site_b},
        )
        db.execute(
            text(
                "DELETE FROM menu_variants WHERE menu_id IN "
                "(SELECT id FROM menus WHERE site_id=:site_id)"
            ),
            {"site_id": site_b},
        )
        db.execute(text("DELETE FROM menus WHERE site_id=:site_id"), {"site_id": site_b})
        db.execute(
            text(
                "INSERT INTO menus(id, tenant_id, site_id, week, year, status) "
                "VALUES (7202, 1, :site_id, 32, 2041, 'published')"
            ),
            {"site_id": site_b},
        )
        db.execute(
            text(
                "INSERT INTO menu_variants(menu_id, day, meal, variant_type, dish_id) "
                "VALUES (7202, 'Mån', 'Lunch', 'alt1', NULL)"
            )
        )
        db.commit()
    finally:
        db.close()

    def snapshot_site_b() -> dict[str, tuple]:
        db = get_session()
        try:
            return {
                "menu": db.execute(
                    text(
                        "SELECT status, updated_at FROM menus "
                        "WHERE id=7202 AND site_id=:site_id"
                    ),
                    {"site_id": site_b},
                ).one(),
                "variants": tuple(
                    db.execute(
                        text(
                            "SELECT day, meal, variant_type, dish_id "
                            "FROM menu_variants WHERE menu_id=7202"
                        )
                    ).fetchall()
                ),
                "links": tuple(
                    db.execute(
                        text(
                            "SELECT builder_menu_id, builder_menu_version, source "
                            "FROM commun_builder_menu_links "
                            "WHERE tenant_id=1 AND site_id=:site_id AND year=2041 AND week=32"
                        ),
                        {"site_id": site_b},
                    ).fetchall()
                ),
                "pins": tuple(
                    db.execute(
                        text(
                            "SELECT builder_menu_id, builder_menu_version "
                            "FROM commun_builder_publication_pins "
                            "WHERE tenant_id=1 AND site_id=:site_id AND year=2041 AND week=32"
                        ),
                        {"site_id": site_b},
                    ).fetchall()
                ),
                "revisions": tuple(
                    db.execute(
                        text(
                            "SELECT builder_menu_id, builder_menu_version, source "
                            "FROM commun_builder_publication_revisions "
                            "WHERE tenant_id=1 AND site_id=:site_id AND year=2041 AND week=32"
                        ),
                        {"site_id": site_b},
                    ).fetchall()
                ),
            }
        finally:
            db.close()

    before = snapshot_site_b()
    query = "?site_id=" + site_b
    publish = client.post(
        "/ui/admin/menu-import/week/2041/32/publish" + query,
        headers={**ADMIN_HEADERS, "If-Match": "not-the-target-etag"},
    )
    assert publish.status_code == 403

    unpublish = client.post(
        "/ui/admin/menu-import/week/2041/32/unpublish" + query,
        data={"_confirm_unpublish": "1", "_etag": "not-the-target-etag"},
        headers=ADMIN_HEADERS,
    )
    assert unpublish.status_code == 403
    assert snapshot_site_b() == before


def test_admin_cannot_publish_or_unpublish_cross_tenant_menu(app_session):
    site_a = "cross-tenant-publish-site-a"
    site_b = "cross-tenant-publish-site-b"
    client = _client_for_site(app_session, site_a)
    db = get_session()
    try:
        db.execute(
            text("INSERT OR IGNORE INTO tenants(id, name) VALUES (2, 'Cross tenant B')")
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO sites(id, name, tenant_id, version) "
                "VALUES (:site_a, 'Site A', 1, 0), "
                "(:site_b, 'Site B', 2, 0)"
            ),
            {"site_a": site_a, "site_b": site_b},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO menus "
                "(id, tenant_id, site_id, week, year, status) "
                "VALUES (7301, 1, :site_a, 34, 2041, 'draft'), "
                "(7302, 2, :site_b, 34, 2041, 'published')"
            ),
            {"site_a": site_a, "site_b": site_b},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO menu_variants "
                "(id, menu_id, day, meal, variant_type, dish_id) "
                "VALUES (7301, 7301, 'Mån', 'Lunch', 'alt1', NULL), "
                "(7302, 7302, 'Mån', 'Lunch', 'alt1', NULL)"
            )
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO commun_builder_menu_links "
                "(id, tenant_id, site_id, year, week, legacy_menu_id, "
                "builder_menu_id, builder_menu_version, source, projection_version, "
                "created_at, updated_at) "
                "VALUES ('cross-tenant-link', 2, :site_b, 2041, 34, 7302, "
                "'builder-cross-tenant', 1, 'pilot', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"site_b": site_b},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO commun_builder_publication_pins "
                "(id, tenant_id, site_id, year, week, legacy_menu_id, "
                "builder_menu_id, builder_menu_version, source, created_at, updated_at) "
                "VALUES ('cross-tenant-pin', 2, :site_b, 2041, 34, 7302, "
                "'builder-cross-tenant', 1, 'pilot', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"site_b": site_b},
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO commun_builder_publication_revisions "
                "(id, tenant_id, site_id, year, week, legacy_menu_id, "
                "builder_menu_id, builder_menu_version, source, created_at, updated_at) "
                "VALUES (7302, 2, :site_b, 2041, 34, 7302, "
                "'builder-cross-tenant', 1, 'pilot', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"site_b": site_b},
        )
        db.commit()
    finally:
        db.close()

    def snapshot(site_id: str, tenant_id: int) -> dict[str, tuple]:
        db = get_session()
        try:
            return {
                "menu": tuple(
                    db.execute(
                        text(
                            "SELECT status, updated_at FROM menus "
                            "WHERE tenant_id=:tenant_id AND site_id=:site_id "
                            "AND year=2041 AND week=34"
                        ),
                        {"tenant_id": tenant_id, "site_id": site_id},
                    ).one()
                ),
                "variants": tuple(
                    db.execute(
                        text(
                            "SELECT day, meal, variant_type, dish_id "
                            "FROM menu_variants WHERE menu_id=7302"
                        )
                    ).fetchall()
                ),
                "links": tuple(
                    db.execute(
                        text(
                            "SELECT builder_menu_id, builder_menu_version, source "
                            "FROM commun_builder_menu_links "
                            "WHERE tenant_id=:tenant_id AND site_id=:site_id "
                            "AND year=2041 AND week=34"
                        ),
                        {"tenant_id": tenant_id, "site_id": site_id},
                    ).fetchall()
                ),
                "pins": tuple(
                    db.execute(
                        text(
                            "SELECT builder_menu_id, builder_menu_version "
                            "FROM commun_builder_publication_pins "
                            "WHERE tenant_id=:tenant_id AND site_id=:site_id "
                            "AND year=2041 AND week=34"
                        ),
                        {"tenant_id": tenant_id, "site_id": site_id},
                    ).fetchall()
                ),
                "revisions": tuple(
                    db.execute(
                        text(
                            "SELECT builder_menu_id, builder_menu_version, source "
                            "FROM commun_builder_publication_revisions "
                            "WHERE tenant_id=:tenant_id AND site_id=:site_id "
                            "AND year=2041 AND week=34"
                        ),
                        {"tenant_id": tenant_id, "site_id": site_id},
                    ).fetchall()
                ),
            }
        finally:
            db.close()

    before = snapshot(site_b, 2)
    query = "?site_id=" + site_b
    publish = client.post(
        "/ui/admin/menu-import/week/2041/34/publish" + query,
        headers={**ADMIN_HEADERS, "If-Match": 'W/"menu-7302-foreign"'},
    )
    assert publish.status_code == 403

    unpublish = client.post(
        "/ui/admin/menu-import/week/2041/34/unpublish" + query,
        data={"_confirm_unpublish": "1", "_etag": 'W/"menu-7302-foreign"'},
        headers=ADMIN_HEADERS,
    )
    assert unpublish.status_code == 403
    assert snapshot(site_b, 2) == before
