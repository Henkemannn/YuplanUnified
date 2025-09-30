import sqlite3
import rotation
import pytest

def force_login(client, user_id=1):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['role'] = 'user'

@pytest.fixture
def metrics_app(app_client, tmp_db_path):
    # Utöka users med rig_id / role / email som tidigare test gjorde
    conn = sqlite3.connect(tmp_db_path.as_posix())
    cols = [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()]
    if 'rig_id' not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN rig_id INTEGER")
    if 'role' not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT")
    if 'email' not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
    conn.execute("UPDATE users SET rig_id=1, role='user', email='anna@example.com' WHERE id=1")
    # Create new tables by running migration snippet (simulate ensure). We'll just execute the 003 file.
    # Minimal inline create (mirrors needed columns):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS service_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rig_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            meal TEXT NOT NULL,
            dish_id INTEGER,
            category TEXT,
            guest_count INTEGER NOT NULL,
            produced_qty_kg REAL,
            served_qty_kg REAL,
            leftover_qty_kg REAL,
            served_g_per_guest REAL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS normative_portion_guidelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rig_id INTEGER,
            category TEXT NOT NULL,
            protein_source TEXT,
            baseline_g_per_guest INTEGER NOT NULL,
            protein_per_100g REAL,
            valid_from TEXT,
            source TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit(); conn.close()
    return app_client


def test_log_and_recommend(metrics_app):
    client = metrics_app
    force_login(client)
    # Logg en service med 50 gäster fisk + kott
    payload = {
        'date': '2025-09-15',
        'meal': 'lunsj',
        'guest_count': 50,
        'dishes': [
            { 'category': 'fisk', 'produced_qty_kg': 8.0, 'leftover_qty_kg': 2.0 },  # served 6 kg => 120 g/gäst
            { 'category': 'kott', 'produced_qty_kg': 9.0, 'leftover_qty_kg': 1.5 }   # served 7.5 kg => 150 g/gäst
        ]
    }
    r = client.post('/service/log', json=payload)
    assert r.status_code == 200
    data = r.get_json(); assert data['ok'] is True
    # Hent recommendation for 60 gäster
    rec = client.get('/service/recommendation?guest_count=60')
    assert rec.status_code == 200
    rec_js = rec.get_json(); assert rec_js['ok'] is True
    # Finn fisk & kott poster
    cats = {item['category']: item for item in rec_js['recommendations']}
    assert 'fisk' in cats and 'kott' in cats
    # Empiriska g per gäst ska reflektera vår logg (dock trimmed mean == value då 1 datapunkt)
    assert cats['fisk']['empirical_g_per_guest'] in (119.9,120,120.0)
    assert cats['kott']['empirical_g_per_guest'] in (149.9,150,150.0)
    # Blended bør ligge mellom baseline (160/170) og empirical
    assert cats['fisk']['blended_g_per_guest'] >= cats['fisk']['empirical_g_per_guest']
    assert cats['kott']['blended_g_per_guest'] >= cats['kott']['empirical_g_per_guest']
