from flask.testing import FlaskClient
from sqlalchemy import text

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_basics():
    from core.db import get_session
    conn = get_session()
    try:
        conn.execute(text("INSERT OR IGNORE INTO sites(id, name) VALUES ('site-alt2-save','Alt2 Save Site')"))
        conn.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES ('dept-alt2-save','site-alt2-save','Save Dept','fixed', 5, NULL, 0)"))
        conn.commit()
    finally:
        conn.close()


def test_admin_alt2_save_roundtrip(app_session, client_admin: FlaskClient):
    _seed_basics()
    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-alt2-save"
    # Save Mon + Wed
    r_save = client_admin.post(
        "/ui/admin/departments/dept-alt2-save/alt2",
        headers=ADMIN_HEADERS,
        json={"year": 2024, "week": 1, "alt2_days": ["mon", "wed"]},
    )
    assert r_save.status_code in (200, 201)
    data_save = r_save.get_json()
    assert set(data_save.get("alt2_days") or []) == {"mon", "wed"}
    # Get again and verify
    r_get = client_admin.get(
        "/ui/admin/departments/dept-alt2-save/alt2?year=2024&week=1",
        headers=ADMIN_HEADERS,
    )
    assert r_get.status_code == 200
    data_get = r_get.get_json()
    assert set(data_get.get("alt2_days") or []) == {"mon", "wed"}


def test_admin_alt2_save_roundtrip_canonical_mirror_current_schema(app_session, client_admin: FlaskClient):
    from core.db import get_session

    conn = get_session()
    try:
        conn.execute(text("INSERT OR REPLACE INTO sites(id, name) VALUES ('site-alt2-legacy-save','Alt2 Legacy Save Site')"))
        conn.execute(text("INSERT OR REPLACE INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, notes, version) VALUES ('dept-alt2-legacy-save','site-alt2-legacy-save','Legacy Save Dept','fixed', 5, NULL, 0)"))
        conn.commit()
    finally:
        conn.close()

    with client_admin.session_transaction() as sess:
        sess["site_id"] = "site-alt2-legacy-save"

    r_save = client_admin.post(
        "/ui/admin/departments/dept-alt2-legacy-save/alt2",
        headers=ADMIN_HEADERS,
        json={"year": 2026, "week": 13, "alt2_days": ["mon", "wed"]},
    )
    assert r_save.status_code in (200, 201)
    data_save = r_save.get_json() or {}
    assert set(data_save.get("alt2_days") or []) == {"mon", "wed"}
    assert data_save.get("choices", {}).get("mon") == "Alt2"
    assert data_save.get("choices", {}).get("wed") == "Alt2"
    assert data_save.get("choices", {}).get("tue") == "Alt1"

    r_get = client_admin.get(
        "/ui/admin/departments/dept-alt2-legacy-save/alt2?year=2026&week=13",
        headers=ADMIN_HEADERS,
    )
    assert r_get.status_code == 200
    data_get = r_get.get_json() or {}
    assert set(data_get.get("alt2_days") or []) == {"mon", "wed"}
    assert data_get.get("choices", {}).get("tue") == "Alt1"
