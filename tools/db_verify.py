import os, sys
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from core.app_factory import create_app
from core.db import get_session
from core.models import User
from werkzeug.security import check_password_hash

def main():
    os.environ.setdefault('APP_ENV','dev')
    os.environ.setdefault('YUPLAN_DEV_HELPERS','1')
    app = create_app({"TESTING": False})
    with app.app_context():
        db = get_session()
        rows = db.query(User).order_by(User.id).all()
        print("USERS:")
        for u in rows:
            print(u.id, u.email, u.role)
        email = "Henrik.Jonsson@Yuplan.se".lower()
        u = db.query(User).filter(User.email==email).first()
        if u:
            ok = check_password_hash(u.password_hash, "G0teb0rg031")
            print("VERIFY:", u.id, u.email, u.role, "password_ok=", ok)
        else:
            print("VERIFY: user not found")

if __name__ == '__main__':
    main()
