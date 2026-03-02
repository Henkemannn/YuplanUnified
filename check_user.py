import sqlite3

email = "Henrik.jonsson@yuplan.se"

con = sqlite3.connect("dev.db")
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
print("has users table:", bool(cur.fetchone()))

cur.execute("PRAGMA table_info(users)")
cols = [r[1] for r in cur.fetchall()]
print("users cols:", cols)

email_col = next((c for c in ["email","username","user_email","login","mail"] if c in cols), None)
print("email_col:", email_col)

if email_col:
    cur.execute(f"SELECT id,{email_col} FROM users WHERE lower({email_col})=lower(?)", (email,))
    print("superuser row:", cur.fetchone())

con.close()