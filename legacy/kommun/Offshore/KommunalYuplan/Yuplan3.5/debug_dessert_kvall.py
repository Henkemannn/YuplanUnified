# Copyright (c) 2025 Henrik Jonsson, Yuplan. All rights reserved.
# Proprietary and confidential. Unauthorized copying, distribution or use is strictly prohibited.
import sqlite3

conn = sqlite3.connect('kost.db')
c = conn.cursor()

print("Vecka | Dag | Typ     | Menytext")
print("------------------------------------------")
for row in c.execute("SELECT vecka, dag, alt_typ, menytext FROM veckomeny WHERE alt_typ IN ('Dessert','Kväll') ORDER BY vecka, dag"):
    print(f"{row[0]:<5} | {row[1]:<3} | {row[2]:<7} | {row[3]}")

conn.close()
