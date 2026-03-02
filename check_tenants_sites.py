import sqlite3

con = sqlite3.connect("dev.db")
cur = con.cursor()

def has_col(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return col in [r[1] for r in cur.fetchall()]

print("\nTENANTS:")
cur.execute("SELECT id, name FROM tenants ORDER BY id")
print(cur.fetchall())

print("\nSITES (id, tenant_id, name):")
cols = ["id", "tenant_id", "name"]
extra = []
if has_col("sites", "deleted_at"):
    extra.append("deleted_at")
if has_col("sites", "created_at"):
    extra.append("created_at")
sel = ", ".join(cols + extra)
cur.execute(f"SELECT {sel} FROM sites ORDER BY tenant_id, name")
rows = cur.fetchall()
for r in rows:
    print(r)

print("\nSITES PER TENANT:")
cur.execute("SELECT tenant_id, COUNT(*) FROM sites GROUP BY tenant_id ORDER BY tenant_id")
print(cur.fetchall())

print("\nLOOKUP KAKTUSEN by id/name:")
q = f"SELECT {sel} FROM sites WHERE lower(id)=lower(?) OR lower(name)=lower(?)"
cur.execute(q, ("kaktusen", "kaktusen"))
print(cur.fetchall())

con.close()