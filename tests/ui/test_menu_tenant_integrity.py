import io
from pathlib import Path

from sqlalchemy import text

from core.app_factory import create_app
from core.db import create_all
from core.importers.docx_importer import DocxMenuImporter


SAMPLE_CSV = """Year,Week,Weekday,Meal,Alt,Text
2026,9,Måndag,Lunch,Alt1,Pasta bolognese
2026,9,Måndag,Lunch,Alt2,Vegetarisk pasta
2026,9,Måndag,Lunch,Dessert,Fruktsallad
"""


def test_menu_import_uses_site_tenant_id_and_publish():
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///:memory:"})
    with app.app_context():
        create_all()
        from core.db import get_session
        from core.models import Tenant

        db = get_session()
        try:
            tenant1 = Tenant(name="Tenant One")
            tenant2 = Tenant(name="Tenant Two")
            db.add_all([tenant1, tenant2])
            db.flush()
            tenant_id = int(tenant2.id)
            db.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id, version) VALUES(:id,:n,:t,0)"
                ),
                {"id": "pilotsite", "n": "Pilot Site", "t": tenant_id},
            )
            db.commit()
        finally:
            db.close()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = "pilotsite"

    data = {"menu_file": (io.BytesIO(SAMPLE_CSV.encode("utf-8")), "menu.csv")}
    resp = client.post(
        "/ui/admin/menu-import/upload",
        data=data,
        content_type="multipart/form-data",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )
    assert resp.status_code in (302, 200)

    list_resp = client.get(
        "/ui/admin/menu-import",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )
    assert list_resp.status_code == 200
    html = list_resp.data.decode("utf-8")
    assert "Vecka 9" in html
    assert "UTKAST" in html

    week_resp = client.get(
        "/ui/admin/menu-import/week/2026/9",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )
    assert week_resp.status_code == 200
    etag = week_resp.headers.get("ETag")
    assert etag

    pub = client.post(
        "/ui/admin/menu-import/week/2026/9/publish",
        headers={
            "X-User-Role": "admin",
            "X-Tenant-Id": "2",
            "If-Match": etag,
        },
    )
    assert pub.status_code in (302, 200)

    list_pub = client.get(
        "/ui/admin/menu-import",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "2"},
    )
    assert list_pub.status_code == 200
    html_pub = list_pub.data.decode("utf-8")
    assert "Vecka 9" in html_pub
    assert "PUBLICERAD" in html_pub

    with app.app_context():
        from core.db import get_session
        from core.menu_service import MenuServiceDB

        db = get_session()
        try:
            row = db.execute(
                text(
                    "SELECT tenant_id FROM menus WHERE site_id=:sid AND week=9 AND year=2026"
                ),
                {"sid": "pilotsite"},
            ).fetchone()
            assert row is not None
            assert int(row[0]) == 2
        finally:
            db.close()

        svc = MenuServiceDB()
        week_view = svc.get_week_view(tenant_id=2, site_id="pilotsite", week=9, year=2026)
        assert week_view.get("days")


def test_docx_import_filters_footer_and_keeps_sunday_lunch():
    matsedel_path = (
        Path(__file__).resolve().parents[1] / "fixtures" / "docx" / "Matsedel_v8-15.docx"
    )
    data = matsedel_path.read_bytes()
    importer = DocxMenuImporter()
    result = importer.parse(data, matsedel_path.name)
    assert result.weeks

    week10 = next((w for w in result.weeks if int(w.week) == 10), None)
    assert week10 is not None

    sunday_lunch = next(
        (
            i
            for i in week10.items
            if str(i.day).lower() == "sunday" and i.meal == "lunch" and i.dish_name == "Fläskköttsgryta med potatis"
        ),
        None,
    )
    assert sunday_lunch is not None

    for week in result.weeks:
        for item in week.items:
            assert "Allt med röd text" not in item.dish_name
