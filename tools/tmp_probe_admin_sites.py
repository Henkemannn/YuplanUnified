import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from core import create_app

app = create_app({"TESTING": True, "SECRET_KEY": "x"})
client = app.test_client()
# Seed one site via POST
client.post("/admin/sites", headers={"X-User-Role":"admin","X-Tenant-Id":"1"}, json={"name":"S1"})
r = client.get("/admin/sites", headers={"X-User-Role":"editor","X-Tenant-Id":"1"})
print("status:", r.status_code)
print("ctype:", r.headers.get("Content-Type"))
print("headers:", {k:v for k,v in r.headers.items() if k in ("ETag","Retry-After","X-Request-Id","Cache-Control","Content-Type")})
print("body:", r.get_data(as_text=True)[:400])
