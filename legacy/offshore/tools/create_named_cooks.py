import sqlite3
from pathlib import Path

try:
    from werkzeug.security import generate_password_hash
except Exception as e:
    raise SystemExit(f"Werkzeug is required (Flask dependency). Import error: {e}")


def main() -> int:
    # Resolve DB path relative to this file (parent dir holds app.db)
    db_path = Path(__file__).resolve().parent.parent / "app.db"
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON;")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Ensure there is a rig to attach users to
    rig_id = None
    row = cur.execute(
        "SELECT rig_id FROM users WHERE role='admin' AND rig_id IS NOT NULL LIMIT 1"
    ).fetchone()
    if row and row["rig_id"] is not None:
        rig_id = row["rig_id"]
    else:
        r = cur.execute("SELECT id FROM rigs ORDER BY id LIMIT 1").fetchone()
        if r:
            rig_id = r["id"]
    if rig_id is None:
        cur.execute(
            "INSERT INTO rigs(name, description) VALUES (?, ?)",
            ("Test Rig", "Auto-created for test cooks"),
        )
        rig_id = cur.lastrowid
        con.commit()

    names = ["Henrik", "Alex", "Cedric", "Ilpo", "Mange", "Johnny"]
    password = "test1234"
    created = 0
    skipped = 0
    for name in names:
        email = f"{name.lower()}@example.local"
        exists = cur.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
        if exists:
            skipped += 1
            continue
        cur.execute(
            "INSERT INTO users (email, name, password_hash, role, rig_id) VALUES (?,?,?,?,?)",
            (email, name, generate_password_hash(password), "user", rig_id),
        )
        created += 1

    con.commit()
    print(f"Using rig_id={rig_id}")
    print(f"Created {created}, skipped {skipped}")
    print("Logins:")
    for name in names:
        print(f"  {name.lower()}@example.local / {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
