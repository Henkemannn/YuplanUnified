import sqlite3
conn = sqlite3.connect('dev.db')
cur = conn.cursor()
print('TABLES')
for (name,) in cur.execute("select name from sqlite_master where type='table' order by name").fetchall():
    if 'weekview' in name or 'resident' in name or 'special' in name or 'planera' in name:
        print(name)
print('--- COLUMNS FOR CANDIDATE TABLES ---')
for t in ['weekview_residents_count','weekview_residents_counts','weekview_residents_count_special','weekview_residents_special','weekview_special_diets','weekview_diet_deviations']:
    try:
        cols = cur.execute(f"pragma table_info({t})").fetchall()
        if cols:
            print(t, [c[1] for c in cols])
    except Exception:
        pass
conn.close()
