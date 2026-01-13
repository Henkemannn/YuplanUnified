from sqlalchemy import text

def test_weekview_menu_modal_icon_and_container(client_admin):
    app = client_admin.application
    from core.db import get_session
    from core.menu_repo import MenuRepo
    with app.app_context():
        db = get_session()
        try:
            # Minimal site/department
            db.execute(text("CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY, name TEXT, version INTEGER)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, site_id TEXT, name TEXT, resident_count_mode TEXT, resident_count_fixed INTEGER, version INTEGER, notes TEXT)"))
            db.execute(text("INSERT OR REPLACE INTO sites(id,name,version) VALUES('site-x','Varberg',0)"))
            db.execute(text("INSERT OR REPLACE INTO departments(id,site_id,name,resident_count_mode,resident_count_fixed,version,notes) VALUES('dep-x','site-x','Avd X','fixed',0,0,'')"))
            db.commit()
        finally:
            db.close()
        # Seed a menu for Tuesday (day=2)
        repo = MenuRepo()
        repo.upsert_menu_item(site_id='site-x', year=2026, week=2, day=2, meal='lunch', alt1_text='Pasta', alt2_text='Sallad', dessert='Kaka')
        repo.upsert_menu_item(site_id='site-x', year=2026, week=2, day=2, meal='dinner', alt1_text='Soppa', alt2_text='Bröd', dessert='')

    # Render weekview all-departments
    resp = client_admin.get(
        "/ui/weekview",
        query_string={"site_id": "site-x", "department_id": "", "year": 2026, "week": 2},
        headers={
            "X-User-Role": "admin",
            "X-Tenant-Id": "1",
            "X-Site-Id": "site-x",
        },
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Icon should render in the Tuesday header (data-day="2") for seeded menu
    assert 'class="ua-icon-btn js-open-modal js-open-menu-modal"' in html
    assert 'data-day="2"' in html
    # Modal container should be present
    assert 'id="menu-day-modal-' in html
    assert 'Meny –' in html
