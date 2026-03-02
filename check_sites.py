import sqlite3

con = sqlite3.connect("dev.db")
cur = con.cursor()

# 1) vilka users finns (id, tenant_id, email, role)
cur.execute("SELECT id, tenant_id, email, role, is_active FROM users ORDER BY id")
users = cur.fetchall()
print("USERS:")
for r in users:
    print(r)

# 2) vilka tenants finns
cur.execute("SELECT id, name FROM tenants ORDER BY id")
print("\nTENANTS:", cur.fetchall())

# 3) hur många sites per tenant
cur.execute("SELECT tenant_id, COUNT(*) FROM sites GROUP BY tenant_id ORDER BY tenant_id")
print("\nSITES PER TENANT:", cur.fetchall())

# 4) visa några sites
cur.execute("SELECT id, tenant_id, name FROM sites ORDER BY tenant_id, name LIMIT 10")
print("\nSAMPLE SITES:", cur.fetchall())

con.close()