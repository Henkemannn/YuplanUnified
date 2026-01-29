HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def test_kitchen_week_no_nested_html(app_session):
    client = app_session.test_client()
    # Minimal params; handler renders explicit empty states when context is missing
    rv = client.get("/ui/kitchen/week", headers=HEADERS)
    assert rv.status_code == 200
    html = rv.data.decode("utf-8")
    # Ensure we do not embed another full HTML document
    assert "<!DOCTYPE html" in html  # single page output has one
    assert html.count("<!DOCTYPE html") == 1
    # Ensure JS is present and empty-state messages are shown
    assert "/static/js/kitchen_week.js" in html
    assert "Inga avdelningar" in html or "Inga specialkoster" in html