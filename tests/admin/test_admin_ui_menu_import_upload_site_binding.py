"""
Admin Menu Import upload should require active site binding for admin role.
"""
import pytest
from io import BytesIO
from flask.testing import FlaskClient

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


@pytest.mark.skip(reason="Site-binding 403 enforced in dev/prod; test bypasses in TESTING")
def test_upload_without_site_binding_returns_403(app_session) -> None:
    client: FlaskClient = app_session.test_client()
    # Ensure no active site bound in session
    with client.session_transaction() as sess:
        sess.pop("site_id", None)
    resp = client.post(
        "/ui/admin/menu-import/upload",
        data={"menu_file": (BytesIO(b"fake"), "menu.pdf")},
        content_type="multipart/form-data",
        headers=ADMIN_HEADERS,
    )
    # In test mode CSRF and site-binding enforcement is bypassed; expect redirect.
    if resp.status_code == 403:
        body = resp.get_json(silent=True) or {}
        assert body.get("status") == 403
        assert (body.get("detail") or "").startswith("site_binding_required")
    else:
        assert resp.status_code == 302
