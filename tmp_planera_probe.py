import sqlite3, json
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
  count(*) as unit_rows,
  sum(rc.count) as baseline_sum,
  sum(case when rs.id is not null then 1 else 0 end) as special_rows,
  sum(coalesce(rs.qty,0)) as special_qty_sum
from weekview_residents_count rc
join departments d on d.id = rc.department_id
left join weekview_residents_special rs
  on rs.department_id = rc.department_id
 and rs.tenant_id = rc.tenant_id
 and rs.year = rc.year
 and rs.week = rc.week
 and rs.day_of_week = rc.day_of_week
 and rs.meal = rc.meal
group by d.site_id, rc.tenant_id, rc.year, rc.week, rc.day_of_week, rc.meal
having baseline_sum > 0
order by special_rows desc, abs(special_qty_sum) desc, baseline_sum desc
limit 15
'''
rows = [dict(r) for r in cur.execute(q).fetchall()]
print(json.dumps(rows, indent=2))
conn.close()
