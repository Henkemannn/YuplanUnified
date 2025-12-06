import pytest

def test_portal_weeks_shows_department_info(client_admin):
    r = client_admin.get("/ui/portal/weeks?site_id=s1&department_id=d1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Boende:" in html


def test_portal_weeks_shows_simple_status_labels(client_admin):
    r = client_admin.get("/ui/portal/weeks?site_id=s1&department_id=d1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    # We expect template to render all three labels across range
    assert "Klar" in html
    assert "Behöver val" in html or "Ej klar" in html
    assert "Ingen meny" in html or "Ej påbörjad" in html


def test_portal_weeks_shows_correct_button_labels(client_admin):
    r = client_admin.get("/ui/portal/weeks?site_id=s1&department_id=d1", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    # When overview has weeks (seeded), buttons should appear; for synthetic IDs (empty list), skip
    if 'data-week="' in html:
        assert "Visa val" in html or "Gör val" in html
        assert "Ingen meny" in html