import sqlite3, json
from datetime import date
conn = sqlite3.connect('dev.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for t in ['weekview_items','weekview_residents_count','weekview_registrations','weekview_alt2_flags','weekview_versions']:
    cols = [r['name'] for r in cur.execute(f"pragma table_info({t})").fetchall()]
    print(t, cols)

print('--- TOP SPECIAL CANDIDATES FROM weekview_items (marked=1, resident_count>0) ---')
q = '''
select
  d.site_id as site_id,
  wi.tenant_id as tenant_id,
  wi.year as year,
  wi.week as week,
  wi.day_of_week as day_of_week,
  wi.meal as meal,
  count(*) as marked_rows,
  sum(wi.resident_count) as marked_qty,
  count(distinct wi.department_id) as marked_units
from weekview_items wi
join departments d on d.id = wi.department_id
where coalesce(wi.marked,0)=1 and coalesce(wi.resident_count,0)>0
group by d.site_id, wi.tenant_id, wi.year, wi.week, wi.day_of_week, wi.meal
order by marked_qty desc, marked_rows desc
limit 20
'''
rows = [dict(r) for r in cur.execute(q).fetchall()]
for r in rows:
    y,w,dow = int(r['year']), int(r['week']), int(r['day_of_week'])
    r['iso_date'] = date.fromisocalendar(y,w,dow).isoformat()
print(json.dumps(rows, indent=2))

print('--- TOP BASELINE FROM weekview_residents_count ---')
q2 = '''
select d.site_id as site_id, rc.tenant_id, rc.year, rc.week, rc.day_of_week, rc.meal,
       count(*) as unit_rows, sum(rc.count) as baseline_sum
from weekview_residents_count rc
join departments d on d.id = rc.department_id
group by d.site_id, rc.tenant_id, rc.year, rc.week, rc.day_of_week, rc.meal
having baseline_sum > 0
order by baseline_sum desc
limit 20
'''
rows2 = [dict(r) for r in cur.execute(q2).fetchall()]
for r in rows2:
    y,w,dow = int(r['year']), int(r['week']), int(r['day_of_week'])
    r['iso_date'] = date.fromisocalendar(y,w,dow).isoformat()
print(json.dumps(rows2, indent=2))
conn.close()
