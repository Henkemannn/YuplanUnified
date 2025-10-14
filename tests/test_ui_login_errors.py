def test_login_problem_details_markup_present(client_admin):
    # Ensure page renders and includes error container markup ids
    r = client_admin.get("/ui/login", headers={"X-User-Role": "admin", "X-Tenant-Id": "1"})
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert 'id="login-error"' in html
    assert 'id="login-error-title"' in html
    assert 'id="login-error-detail"' in html
    # caps lock hint exists (hidden by default)
    assert 'id="capslock-hint"' in html
