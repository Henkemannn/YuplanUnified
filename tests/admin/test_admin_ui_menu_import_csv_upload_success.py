from flask.testing import FlaskClient
from io import BytesIO
import os

ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def test_csv_upload_returns_success(app_session) -> None:
    client: FlaskClient = app_session.test_client()
    # Load fixture CSV
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_menu.csv")
    with open(fixture_path, "rb") as f:
        data = {"menu_file": (BytesIO(f.read()), "sample_menu.csv")}
    resp = client.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type="multipart/form-data",
        headers=ADMIN_HEADERS,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    # Verify success by presence of imported week in the list
    assert "Importerade menyer" in html
    assert "2025" in html and "49" in html
