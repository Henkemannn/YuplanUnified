import sqlite3, json
conn = sqlite3.connect('dev.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
rows1=[dict(r) for r in cur.execute("""
select tenant_id, department_id, year, week, day_of_week, meal, count
from weekview_residents_count
where tenant_id='1' and department_id='dep-A' and year=2025 and week=10 and day_of_week=1 and meal='lunch'
""").fetchall()]
rows2=[dict(r) for r in cur.execute("""
select tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked
from weekview_registrations
where tenant_id='1' and department_id='dep-A' and year=2025 and week=10 and day_of_week=1 and meal='lunch'
order by diet_type
""").fetchall()]
print(json.dumps({'residents_rows':rows1,'registration_rows':rows2}, indent=2))
conn.close()
