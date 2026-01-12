from io import BytesIO


def test_customer_admin_upload_docx_not_403(client_admin):
    # Provide a valid CSRF token via session + header (double-submit)
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tok-admin-upload"
    data = {
        "menu_file": (BytesIO(b"PK\x03\x04dummy-docx"), "menu.docx"),
        "csrf_token": "tok-admin-upload",
    }
    resp = client_admin.post(
        "/ui/admin/menu-import/upload",
        data=data,
        headers={
            "X-User-Role": "admin",
            "X-Tenant-Id": "1",
            "X-Site-Id": "site-x",
            "X-CSRF-Token": "tok-admin-upload",
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    # Should not be blocked by CSRF (previously 403); route may redirect on success
    assert resp.status_code != 403
    assert resp.status_code in (200, 302, 303)
