def test_weekview_overview_derives_site_from_session(app_session, client_admin):
    # Arrange: ensure session already has a bound site via client_admin fixture
    # Also set minimal auth context required by route (role + tenant)
    with client_admin.session_transaction() as sess:
        sess["role"] = "admin"
        sess["tenant_id"] = 1
        sess["site_lock"] = True
        sess["user_id"] = 12345
    # Act: request overview WITHOUT site_id in query
    resp = client_admin.get("/ui/weekview_overview?year=2026&week=4")

    # Assert: OK and page structure rendered (header + day cells)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Stable markers: title contains week number and container for day cells exists
    assert "Weekview Översikt – Vecka 4" in html
    assert "weekview-overview-day-cell" in html
