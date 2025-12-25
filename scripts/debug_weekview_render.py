from __future__ import annotations

import os
from datetime import date as _date

import sys
import os as _os
sys.path.append(_os.getcwd())
from core import create_app
from core.admin_repo import SitesRepo, DepartmentsRepo, DietTypesRepo

# App + client
app = create_app({"TESTING": True})
client = app.test_client()

# Seed minimal data
srepo = SitesRepo()
s, _ = srepo.create_site("DebugSite")

drepo = DepartmentsRepo()
d1, _ = drepo.create_department(site_id=s["id"], name="Avdelning 1", resident_count_mode="fixed", resident_count_fixed=10)
d2, _ = drepo.create_department(site_id=s["id"], name="Avdelning 2", resident_count_mode="fixed", resident_count_fixed=12)

# One diet type
trepo = DietTypesRepo()
dtid = trepo.create(tenant_id=1, name="Glutenfri", default_select=False)
drepo.upsert_department_diet_defaults(d1["id"], 0, [{"diet_type_id": str(dtid), "default_count": 2}])
drepo.upsert_department_diet_defaults(d2["id"], 0, [{"diet_type_id": str(dtid), "default_count": 2}])

iso = _date.today().isocalendar()
year, week = iso[0], iso[1]

# Hit route with empty department_id
resp = client.get(f"/ui/weekview?site_id={s['id']}&department_id=&year={year}&week={week}", headers={"X-User-Role":"admin","X-Tenant-Id":"1","X-User-Id":"1"})
print("STATUS:", resp.status_code)
body = resp.get_data(as_text=True)
print("BODY HEAD:\n", body[:500])
