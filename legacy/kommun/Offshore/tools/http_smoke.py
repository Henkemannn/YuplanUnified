import datetime

import requests

BASE = "http://127.0.0.1:5000"
s = requests.Session()

# 1) Login as admin
r = s.post(f"{BASE}/adminlogin", data={"email":"admin@example.local","password":"test1234"}, allow_redirects=True)
print("Login URL:", r.url, "status:", r.status_code)
r.raise_for_status()

# 1b) Open simple page to confirm route exists and session is admin
routes = s.get(f"{BASE}/__routes", allow_redirects=True)
print("__routes URL:", routes.url, "status:", routes.status_code)
try:
    rjson = routes.json()
    print("Has /turnus/simple?:", any("/turnus/simple" in r for r in rjson.get("routes", [])))
except Exception as e:
    print("Failed to parse routes JSON:", e)

pg = s.get(f"{BASE}/turnus/simple", allow_redirects=True)
print("Simple page URL:", pg.url, "status:", pg.status_code)
pg.raise_for_status()

# 2) Build base plan for next Friday
today = datetime.date.today()
# Find next Friday (weekday=4)
delta = (4 - today.weekday()) % 7
if delta == 0:
    delta = 7
start_friday = (today + datetime.timedelta(days=delta)).strftime("%Y-%m-%d")

bb = s.post(f"{BASE}/turnus/simple/build_base", data={"start_friday": start_friday}, allow_redirects=True)
print("Build base URL:", bb.url, "status:", bb.status_code, "for", start_friday)
bb.raise_for_status()

# 3) Apply to 6 cooks (planned)
ap = s.post(f"{BASE}/turnus/simple/apply", data={"start_friday": start_friday, "status": "planned"}, allow_redirects=True)
print("Apply URL:", ap.url, "status:", ap.status_code)
ap.raise_for_status()

# 4) Fetch preview for current rig by first calling /health then guessing rig_id via a quick probe is not possible; use rig 3 (seeded rig)
rig_id = 3
# Preview next 4 weeks
start = today.strftime("%Y-%m-%d")
end = (today + datetime.timedelta(weeks=4)).strftime("%Y-%m-%d")
r = s.get(f"{BASE}/turnus/preview", params={"rig_id": rig_id, "start": start, "end": end})
r.raise_for_status()
js = r.json()
print("Preview count:", js.get("count"), "ok:", js.get("ok"))
print("First 3 items:", js.get("items", [])[:3])
