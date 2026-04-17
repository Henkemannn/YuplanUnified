import sqlite3, json
from datetime import date
conn = sqlite3.connect('dev.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
q = '''
select rc.tenant_id, rc.department_id, d.site_id, rc.year, rc.week, rc.day_of_week, rc.meal, rc.count
from weekview_residents_count rc
left join departments d on d.id = rc.department_id
where rc.count > 0
order by rc.count desc, rc.year desc, rc.week desc
limit 80
'''
rows=[dict(r) for r in cur.execute(q).fetchall()]
for r in rows:
    r['iso_date']=date.fromisocalendar(int(r['year']),int(r['week']),int(r['day_of_week'])).isoformat()
print('positive_rows', len(rows))
print(json.dumps(rows, indent=2))

q2='''
select tenant_id, department_id, year, week, day_of_week, meal, diet_type, marked
from weekview_registrations
order by year desc, week desc, day_of_week, meal
limit 120
'''
rows2=[dict(r) for r in cur.execute(q2).fetchall()]
print('registrations_rows', len(rows2))
print(json.dumps(rows2, indent=2))
conn.close()
