import os
import sys
# Ensure repository root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from core.app_factory import create_app

# Ensure dev flags
os.environ.setdefault('APP_ENV', 'dev')
os.environ.setdefault('YUPLAN_DEV_HELPERS', '1')
os.environ.setdefault('DEV_CREATE_ALL', '1')
os.environ.setdefault('YUPLAN_SEED_HENRIK', '1')

app = create_app({"TESTING": False})

if __name__ == '__main__':
    with app.app_context():
        c = app.test_client()
        r = c.post('/auth/login', json={"email":"Henrik.Jonsson@Yuplan.se","password":"WrongPass"})
        print("status:", r.status_code)
        try:
            print("body:", r.get_json())
        except Exception:
            print("body:", r.data[:200])
        r2 = c.post('/auth/login', json={"email":"Henrik.Jonsson@Yuplan.se","password":"G0teb0rg031"})
        print("status2:", r2.status_code)
        try:
            print("ok2:", (r2.get_json() or {}).get("ok"))
        except Exception:
            print("body2:", r2.data[:200])
        print("instance_path:", app.instance_path)
        print("auth_debug_log:", os.path.join(app.instance_path, 'auth_debug.log'))
