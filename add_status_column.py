from core.db import get_session
from sqlalchemy import text

db = get_session()
try:
    db.execute(text("ALTER TABLE menus ADD COLUMN status VARCHAR(20) DEFAULT 'draft'"))
    db.commit()
    print("Status column added successfully")
except Exception as e:
    print(f"Error (may already exist): {e}")
finally:
    db.close()
