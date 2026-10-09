from __future__ import annotations

from sqlalchemy import text
from werkzeug.datastructures import MultiDict


ADMIN_HEADERS = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def _seed_site_and_session(app_session, site_id: str) -> None:
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text("INSERT OR REPLACE INTO sites (id, name, tenant_id, version) VALUES (:id, :name, :tid, 0)"),
            {"id": site_id, "name": site_id, "tid": 1},
        )
        db.commit()
    finally:
        db.close()

    client = app_session.test_client()
    with client.session_transaction() as sess:
        sess["site_id"] = site_id
    return client


def _xhr_admin_headers() -> dict[str, str]:
    return {
        **ADMIN_HEADERS,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    }


def _build_form_data(
    *,
    year: int,
    week: int,
    action: str,
    menu_name: str = "",
    row_count: int = 0,
    selected_days: list[str] | None = None,
    row_labels: list[str] | None = None,
) -> list[tuple[str, str]]:
    payload: list[tuple[str, str]] = [
        ("year", str(year)),
        ("week", str(week)),
        ("action", action),
        ("menu_name", menu_name),
        ("row_count", str(row_count)),
    ]
    for day in selected_days or []:
        payload.append(("selected_days", day))
    for label in row_labels or []:
        payload.append(("row_labels", label))
    return MultiDict(payload)


def _seed_existing_menu(site_id: str, year: int, week: int, *, with_variant: bool = False) -> int:
    from core.db import get_session

    db = get_session()
    try:
        db.execute(
            text("INSERT INTO menus (tenant_id, site_id, week, year, status) VALUES (:tid, :sid, :week, :year, :status)"),
            {"tid": 1, "sid": site_id, "week": week, "year": year, "status": "draft"},
        )
        menu_id = db.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
        if with_variant:
            db.execute(
                text("INSERT INTO dishes (tenant_id, name) VALUES (:tid, :name)"),
                {"tid": 1, "name": "Seed dish"},
            )
            dish_id = db.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
            db.execute(
                text(
                    """
                    INSERT INTO menu_variants (menu_id, day, meal, variant_type, dish_id)
                    VALUES (:mid, :day, :meal, :variant_type, :dish_id)
                    """
                ),
                {"mid": menu_id, "day": "monday", "meal": "lunch", "variant_type": "main", "dish_id": dish_id},
            )
        db.commit()
        return int(menu_id)
    finally:
        db.close()


def test_new_menu_preview_create_and_zero_row_editor(app_session):
    client = _seed_site_and_session(app_session, "site-new-menu")

    preview = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(year=2026, week=10, action="preview"),
        headers=ADMIN_HEADERS,
    )

    assert preview.status_code == 200
    preview_payload = preview.get_json()
    assert preview_payload["ok"] is True
    assert preview_payload["status"] == "ready"
    assert preview_payload["menu_name"] == "Vecka 10 / 2026"
    assert preview_payload["week_range"]["label"] == "Vecka 10 · 2 mars–8 mars 2026"

    create = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(
            year=2026,
            week=10,
            action="create",
            menu_name="Testmeny Gate29",
            row_count=3,
            selected_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
            row_labels=["Dagens", "Vegetariskt", "Farmors favorit"],
        ),
        headers=_xhr_admin_headers(),
    )

    assert create.status_code == 200
    create_payload = create.get_json()
    assert create_payload["ok"] is True
    assert create_payload["open_url"].endswith("/ui/admin/menu-import/week/2026/10?edit=1")

    week_page = client.get(create_payload["open_url"], headers=ADMIN_HEADERS)
    assert week_page.status_code == 200
    html = week_page.data.decode("utf-8")
    assert "Testmeny Gate29" in html
    assert "+ Lägg till menyrad" in html
    assert "Lunch alt 1" not in html
    assert 'data-slot-key="lunch_alt1"' not in html
    assert html.count('data-row-kind="dynamic"') == 15
    assert "Dagens" in html
    assert "Vegetariskt" in html
    assert "Farmors favorit" in html

    from core.db import get_session
    from core.models import CommunBuilderMenuLink
    from core.commun_builder_projection import _get_builder_menu_context_flow

    db = get_session()
    try:
        link = db.query(CommunBuilderMenuLink).filter_by(tenant_id=1, site_id="site-new-menu", year=2026, week=10).one()
        assert link.source == "manual"
        assert link.builder_menu_id
    finally:
        db.close()

    with app_session.app_context():
        builder_flow = _get_builder_menu_context_flow()
        rows = builder_flow.list_menu_rows(link.builder_menu_id)
    assert len(rows) == 15
    assert all(row["row_kind"] == "dynamic" for row in rows)
    assert all(row["composition_ref_type"] == "empty" for row in rows)
    assert all(row["composition_id"] is None for row in rows)
    assert [row["sort_order"] for row in rows[:3]] == [10, 20, 30]
    assert [row["display_label"] for row in rows[:3]] == ["Dagens", "Vegetariskt", "Farmors favorit"]
    assert all(row["day"] in {"monday", "tuesday", "wednesday", "thursday", "friday"} for row in rows)
    assert not any(row["day"] in {"saturday", "sunday"} for row in rows)


def test_new_menu_preview_conflict_and_replace_preserves_existing_rows(app_session):
    client = _seed_site_and_session(app_session, "site-new-menu-conflict")
    menu_id = _seed_existing_menu("site-new-menu-conflict", 2026, 11, with_variant=True)

    preview = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(year=2026, week=11, action="preview"),
        headers=ADMIN_HEADERS,
    )

    assert preview.status_code == 200
    preview_payload = preview.get_json()
    assert preview_payload["ok"] is True
    assert preview_payload["status"] == "conflict"
    assert preview_payload["message"] == "Det finns redan en meny för vecka 11 / 2026. Välj en annan vecka."
    assert preview_payload["open_url"].endswith("/ui/admin/menu-import/week/2026/11")

    create = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(
            year=2026,
            week=11,
            action="create",
            menu_name="Testmeny Gate29 replace",
            row_count=1,
            selected_days=["monday"],
            row_labels=["Dagens"],
        ),
        headers=_xhr_admin_headers(),
    )
    assert create.status_code == 409

    open_existing = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(year=2026, week=11, action="open-existing"),
        headers=_xhr_admin_headers(),
    )
    assert open_existing.status_code == 302
    assert open_existing.headers["Location"].endswith("/ui/admin/menu-import/week/2026/11")

    from core.db import get_session

    db = get_session()
    try:
        row_count = db.execute(
            text("SELECT COUNT(*) FROM menu_variants WHERE menu_id=:menu_id"),
            {"menu_id": menu_id},
        ).fetchone()[0]
        assert int(row_count) == 1
    finally:
        db.close()

    week_page = client.get("/ui/admin/menu-import/week/2026/11?edit=1", headers=ADMIN_HEADERS)
    assert week_page.status_code == 200
    html = week_page.data.decode("utf-8")
    assert "Testmeny Gate29" not in html
    assert "+ Lägg till menyrad" in html
    assert "Seed dish" in html


def test_new_menu_blank_name_and_zero_row_fallbacks(app_session):
    client = _seed_site_and_session(app_session, "site-new-menu-fallback")

    preview = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(year=2026, week=12, action="preview"),
        headers=ADMIN_HEADERS,
    )
    preview_payload = preview.get_json()
    assert preview_payload["menu_name"] == "Vecka 12 / 2026"

    create = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(
            year=2026,
            week=12,
            action="create",
            menu_name="",
            row_count=0,
            selected_days=["monday", "tuesday", "wednesday"],
        ),
        headers=_xhr_admin_headers(),
    )
    assert create.status_code == 200
    create_payload = create.get_json()
    assert create_payload["ok"] is True

    week_page = client.get(create_payload["open_url"], headers=ADMIN_HEADERS)
    html = week_page.data.decode("utf-8")
    assert "Vecka 12 / 2026" in html
    assert "+ Lägg till menyrad" in html


def test_new_menu_requires_selected_day_before_create(app_session):
    client = _seed_site_and_session(app_session, "site-new-menu-selected-day")

    create = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(
            year=2026,
            week=13,
            action="create",
            menu_name="TEMP Gate29F",
            row_count=3,
            selected_days=[],
            row_labels=["Dagens", "Vegetariskt", "Farmors favorit"],
        ),
        headers=_xhr_admin_headers(),
    )
    assert create.status_code == 400
    payload = create.get_json()
    assert payload["ok"] is False
    assert payload["error"] == "selected_days_required"


def test_new_menu_blank_row_labels_fallback_to_neutral_names(app_session):
    client = _seed_site_and_session(app_session, "site-new-menu-row-labels")

    create = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(
            year=2026,
            week=13,
            action="create",
            menu_name="Label fallback test",
            row_count=2,
            selected_days=["monday"],
            row_labels=["", ""],
        ),
        headers=_xhr_admin_headers(),
    )
    assert create.status_code == 200
    create_payload = create.get_json()

    from core.db import get_session
    from core.models import CommunBuilderMenuLink
    from core.commun_builder_projection import _get_builder_menu_context_flow

    db = get_session()
    try:
        link = db.query(CommunBuilderMenuLink).filter_by(tenant_id=1, site_id="site-new-menu-row-labels", year=2026, week=13).one()
    finally:
        db.close()

    with app_session.app_context():
        builder_flow = _get_builder_menu_context_flow()
        rows = builder_flow.list_menu_rows(link.builder_menu_id)
    assert [row["display_label"] for row in rows] == ["Menyrad 1", "Menyrad 2"]
    assert len(rows) == 2


def test_new_menu_zero_rows_leave_existing_fallback_empty(app_session):
    client = _seed_site_and_session(app_session, "site-new-menu-fallback-empty")

    create = client.post(
        "/ui/admin/menu-import/new",
        data=_build_form_data(
            year=2026,
            week=12,
            action="create",
            menu_name="",
            row_count=0,
            selected_days=["monday", "tuesday", "wednesday"],
        ),
        headers=_xhr_admin_headers(),
    )
    assert create.status_code == 200
    create_payload = create.get_json()

    from core.db import get_session
    from core.models import CommunBuilderMenuLink
    from core.commun_builder_projection import _get_builder_menu_context_flow

    db = get_session()
    try:
        link = db.query(CommunBuilderMenuLink).filter_by(tenant_id=1, site_id="site-new-menu-fallback-empty", year=2026, week=12).one()
    finally:
        db.close()

    with app_session.app_context():
        builder_flow = _get_builder_menu_context_flow()
        rows = builder_flow.list_menu_rows(link.builder_menu_id)
    assert rows == []


def test_new_menu_modal_defaults_render_all_weekdays_selected(app_session):
    client = _seed_site_and_session(app_session, "site-new-menu-defaults")

    response = client.get("/ui/admin/menu-import", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "+ Skapa meny" in html
    assert 'data-admin-menu-new-name' in html
    assert '7 dagars meny' in html
    assert html.count('data-admin-menu-new-day-toggle') == 7
    assert html.count('type="checkbox"') >= 7
    assert html.count('checked aria-label=') >= 7
    assert 'data-admin-menu-new-row-count' in html
    assert 'value="0"' in html
    assert 'data-admin-menu-new-open' not in html
    assert 'Skapa meny' in html
    assert 'Öppna befintlig' not in html
