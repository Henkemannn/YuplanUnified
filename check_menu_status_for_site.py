import sqlite3

SITE_ID = "pilotsite"   # <- exakt id från tidigare output (('pilotsite', 2, 'Pilotsite'))

con = sqlite3.connect("dev.db")
cur = con.cursor()

cur.execute("SELECT id, tenant_id, name FROM sites WHERE id=?", (SITE_ID,))
print("SITE:", cur.fetchone())

cur.execute("""
    SELECT tenant_id, week, year, status, COUNT(*)
    FROM menus
    WHERE site_id=?
    GROUP BY tenant_id, week, year, status
    ORDER BY year, week, status
""", (SITE_ID,))
rows = cur.fetchall()
print("\nMENUS for site:")
for r in rows:
    print(r)

con.close()