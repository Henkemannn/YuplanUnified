import sqlite3

con = sqlite3.connect("dev.db")
cur = con.cursor()

cur.execute("UPDATE sites SET tenant_id=1 WHERE id='kaktusen'")
con.commit()

print("Updated Kaktusen to tenant_id=1")

con.close()