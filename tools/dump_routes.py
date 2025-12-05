import sys, os
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from core.app_factory import create_app

app = create_app({"TESTING": True})

print("Routes under /portal/*:")
for r in app.url_map.iter_rules():
    if r.rule.startswith('/portal/'):
        methods = ','.join(sorted(m for m in r.methods if m in ('GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS')))
        print(f"{methods:20s} {r.rule:40s} -> {r.endpoint}")
