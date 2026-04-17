import sqlite3, json
from datetime import date
conn = sqlite3.connect('dev.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
q = '''
select
  d.site_id as site_id,
  rc.tenant_id as tenant_id,
  rc.year as year,
  rc.week as week,
  rc.day_of_week as day_of_week,
  rc.meal as meal,
  count(distinct rc.department_id) as unit_rows,
  sum(rc.count) as baseline_sum,
  sum(case when r.marked=1 and lower(coalesce(r.diet_type,'')) <> 'normal' then 1 else 0 end) as marked_special_rows,
  sum(case when r.marked=1 and lower(coalesce(r.diet_type,'')) <> 'normal' then rc.count else 0 end) as marked_special_qty_proxy
from weekview_residents_count rc
join departments d on d.id = rc.department_id
left join weekview_registrations r
  on r.tenant_id = rc.tenant_id
 and r.department_id = rc.department_id
 and r.year = rc.year
 and r.week = rc.week
 and r.day_of_week = rc.day_of_week
 and r.meal = rc.meal
group by d.site_id, rc.tenant_id, rc.year, rc.week, rc.day_of_week, rc.meal
having baseline_sum > 0
order by marked_special_rows desc, marked_special_qty_proxy desc, baseline_sum desc
limit 25
'''
rows = [dict(r) for r in cur.execute(q).fetchall()]
for r in rows:
    y,w,dow = int(r['year']), int(r['week']), int(r['day_of_week'])
    r['iso_date'] = date.fromisocalendar(y,w,dow).isoformat()
print(json.dumps(rows, indent=2))
conn.close()
