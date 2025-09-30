import os, sqlite3
from werkzeug.security import generate_password_hash

DB = os.path.join(os.getcwd(), 'app.db')
admin_email = os.environ.get('SEED_ADMIN_EMAIL', 'admin@example.local').lower()
admin_pw = os.environ.get('SEED_ADMIN_PASSWORD', 'test1234')
rig_name = os.environ.get('SEED_RIG_NAME', 'Test Rig')

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.executescript('''
CREATE TABLE IF NOT EXISTS rigs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT
);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE,
  name TEXT,
  password_hash TEXT,
  role TEXT,
  rig_id INTEGER,
  tenant_id INTEGER DEFAULT 0
);
''')

rig = cur.execute("SELECT id FROM rigs WHERE name=?", (rig_name,)).fetchone()
if not rig:
    cur.execute("INSERT INTO rigs(name, description) VALUES(?, ?)", (rig_name, 'Seeded rig'))
    con.commit()
    rig = cur.execute("SELECT id FROM rigs WHERE name=?", (rig_name,)).fetchone()
rig_id = rig['id']

user = cur.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
if not user:
    cur.execute(
        "INSERT INTO users(email, name, password_hash, role, rig_id) VALUES (?,?,?,?,?)",
        (admin_email, 'Admin', generate_password_hash(admin_pw), 'admin', rig_id)
    )
    con.commit()
    user = cur.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()

print(f"Seed complete. Admin: {admin_email} / {admin_pw}, rig_id={rig_id}")
