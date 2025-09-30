import sqlite3
import rotation
import pytest

# Helper to force-login by setting session (Flask test client context manager pattern)

def login_session(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['role'] = 'user'

@pytest.fixture
def seeded_app(app_client, tmp_db_path):
    # Seed minimal rig/user with required columns for app logic
    conn = sqlite3.connect(tmp_db_path.as_posix())
    conn.execute("ALTER TABLE users ADD COLUMN email TEXT") if 'email' not in [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()] else None
    conn.execute("ALTER TABLE users ADD COLUMN rig_id INTEGER") if 'rig_id' not in [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()] else None
    conn.execute("ALTER TABLE users ADD COLUMN role TEXT") if 'role' not in [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()] else None
    conn.execute("UPDATE users SET rig_id=1, role='user', email='anna@example.com' WHERE id=1")
    # Add rig description if missing
    try:
        conn.execute("ALTER TABLE rigs ADD COLUMN description TEXT")
    except Exception:
        pass
    # create menu_settings minimal so dashboard logic not error when invoked indirectly (optional)
    conn.execute("CREATE TABLE IF NOT EXISTS menu_settings (rig_id INTEGER PRIMARY KEY, start_week INTEGER, start_index INTEGER, menu_json TEXT, updated_at TEXT DEFAULT (datetime('now')))" )
    conn.commit(); conn.close()
    return app_client


def test_create_and_link_recipe(seeded_app):
    client = seeded_app
    # Force session login
    login_session(client, 1)

    # Manually insert a dish into dish_catalog via ensure path (needs rig and slug)
    conn = sqlite3.connect(rotation.DB_PATH.as_posix())
    conn.execute("CREATE TABLE IF NOT EXISTS dish_catalog (id INTEGER PRIMARY KEY AUTOINCREMENT, rig_id INTEGER NOT NULL, slug TEXT NOT NULL, name TEXT NOT NULL, first_seen_date TEXT, active INTEGER DEFAULT 1, recipe_id INTEGER, UNIQUE(rig_id, slug))")
    # Insert sample dish
    conn.execute("INSERT OR IGNORE INTO dish_catalog(rig_id, slug, name, first_seen_date) VALUES(1, 'test-dish', 'Test Dish', date('now'))")
    dish_id = conn.execute("SELECT id FROM dish_catalog WHERE rig_id=1 AND slug='test-dish'").fetchone()[0]
    conn.commit(); conn.close()

    # Create recipe via POST
    resp = client.post('/recipes/new', data={
        'title': 'Test Recipe',
        'raw_text': 'Line1\nLine2',
        'categories': 'fish,hot',
        'method_type': 'base'
    }, follow_redirects=False)
    assert resp.status_code in (302, 303)

    # Find recipe id by querying list page
    resp_list = client.get('/recipes')
    assert resp_list.status_code == 200
    assert b'Test Recipe' in resp_list.data

    # Parse recipe_id from detail redirect location or list (simpler: query DB)
    conn = sqlite3.connect(rotation.DB_PATH.as_posix())
    rid = conn.execute("SELECT id FROM recipes WHERE title='Test Recipe' AND rig_id=1").fetchone()[0]
    conn.close()

    # Link recipe to dish
    resp_link = client.post(f'/dish/{dish_id}/link_recipe', data={'recipe_id': str(rid)}, follow_redirects=False)
    assert resp_link.status_code in (302, 303)

    # Verify linkage
    conn = sqlite3.connect(rotation.DB_PATH.as_posix())
    linked = conn.execute("SELECT recipe_id FROM dish_catalog WHERE id=?", (dish_id,)).fetchone()[0]
    conn.close()
    assert linked == rid

    # Coverage helper should now count 1/1 when invoked via dashboard context (optional smoke)
    dash = client.get('/dashboard')
    assert dash.status_code == 200
    # Not asserting HTML specifics to keep test stable
