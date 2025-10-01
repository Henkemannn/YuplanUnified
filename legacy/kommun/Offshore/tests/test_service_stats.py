import sqlite3

import pytest
from test_service_metrics import force_login  # reuse helper


@pytest.fixture
def stats_app(app_client, tmp_db_path):
    # Ensure extra columns and tables like previous fixture did
    conn = sqlite3.connect(tmp_db_path.as_posix())
    cols = [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "rig_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN rig_id INTEGER")
    if "role" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT")
    if "email" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
    conn.execute("UPDATE users SET rig_id=1, role='user', email='anna@example.com' WHERE id=1")
    # Service + normative tables
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


def _log(client, day, meal, guest_count, dishes):
    return client.post("/service/log", json={
        "date": day,
        "meal": meal,
        "guest_count": guest_count,
        "dishes": dishes
    })


def test_day_stats(stats_app):
    c = stats_app
    force_login(c)
    # seed a day with two meals
    _log(c, "2025-09-15", "lunsj", 40, [
        { "category": "fisk", "produced_qty_kg": 6.0, "leftover_qty_kg": 1.0 },  # served 5kg => 125 g
    ])
    _log(c, "2025-09-15", "middag", 50, [
        { "category": "fisk", "produced_qty_kg": 7.5, "leftover_qty_kg": 2.0 },  # served 5.5kg => 110 g
        { "category": "kott", "produced_qty_kg": 8.0, "leftover_qty_kg": 1.0 },  # served 7kg => 140 g
    ])
    r = c.get("/service/stats?date=2025-09-15&period=day")
    assert r.status_code == 200
    js = r.get_json(); assert js["ok"]
    cats = {row["category"]: row for row in js["stats"]}
    assert "fisk" in cats and "kott" in cats
    # Check served kg aggregation (approx)
    # fisk served: 5 + 5.5 = 10.5
    assert abs(cats["fisk"]["served_kg"] - 10.5) < 0.01
    # kott served: 7
    assert abs(cats["kott"]["served_kg"] - 7.0) < 0.01


def test_week_stats(stats_app):
    c = stats_app
    force_login(c)
    # Monday 15th and Tuesday 16th (assuming 2025-09-15 is Monday for test logic, we just treat as week range anyway)
    _log(c, "2025-09-15", "lunsj", 40, [
        { "category": "fisk", "produced_qty_kg": 6.0, "leftover_qty_kg": 1.0 },
    ])
    _log(c, "2025-09-16", "lunsj", 60, [
        { "category": "fisk", "produced_qty_kg": 9.0, "leftover_qty_kg": 3.0 },  # served 6 => 100 g
        { "category": "extra", "produced_qty_kg": 4.0, "leftover_qty_kg": 0.5 },  # served 3.5 => ~58.3 g
    ])
    r = c.get("/service/stats?date=2025-09-15&period=week")
    assert r.status_code == 200
    js = r.get_json(); assert js["ok"]
    cats = {row["category"]: row for row in js["stats"]}
    assert "fisk" in cats and "extra" in cats
    # Weekly served fisk: day1 5 + day2 6 = 11
    assert abs(cats["fisk"]["served_kg"] - 11.0) < 0.01
    # leftover and produced sanity
    assert cats["extra"]["produced_kg"] >= cats["extra"]["served_kg"]


def test_empty(stats_app):
    c = stats_app
    force_login(c)
    r = c.get("/service/stats?date=2025-09-20&period=day")
    assert r.status_code == 200
    js = r.get_json(); assert js["ok"]
    assert js["stats"] == []
