import sqlite3

con = sqlite3.connect("dev.db")
cur = con.cursor()

# 1) lista sites så du kan se ID:t för nya siten
print("\n--- SITES ---")
cur.execute("SELECT id, tenant_id, name FROM sites ORDER BY name LIMIT 50")
sites = cur.fetchall()
for s in sites:
    print(s)

# 2) hitta tabeller som innehåller "menu"
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
menu_tables = [t for t in tables if "menu" in t.lower()]
print("\n--- MENU TABLES ---")
for t in menu_tables:
    print(t)

# 3) försök hitta kolumnen vecka/week_key i relevanta tabeller och räkna rader per vecka+site
def print_counts(table, site_col, week_col):
    try:
        cur.execute(f"SELECT {site_col}, {week_col}, COUNT(*) FROM {table} GROUP BY {site_col}, {week_col} ORDER BY COUNT(*) DESC LIMIT 30")
        rows = cur.fetchall()
        if rows:
            print(f"\n--- {table} counts by {site_col}/{week_col} ---")
            for r in rows:
                print(r)
    except Exception:
        pass

# vanliga kandidater (anpassa om tabellerna heter annorlunda)
candidates = [
    ("menus", "site_id", "week_key"),
    ("menu_details", "site_id", "week_key"),
    ("menu_weeks", "site_id", "week_key"),
    ("menu_items", "site_id", "week_key"),
]
for t, sc, wc in candidates:
    if t in tables:
        print_counts(t, sc, wc)

con.close()