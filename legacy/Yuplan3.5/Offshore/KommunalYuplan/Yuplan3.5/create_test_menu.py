# Copyright (c) 2025 Henrik Jonsson, Yuplan. All rights reserved.
# Proprietary and confidential. Unauthorized copying, distribution or use is strictly prohibited.
import sqlite3

# Öppna databas
conn = sqlite3.connect('kost.db')
cursor = conn.cursor()

# Skapa veckomeny-tabellen om den inte finns
cursor.execute('''
    CREATE TABLE IF NOT EXISTS veckomeny (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vecka INTEGER NOT NULL,
        dag TEXT NOT NULL,
        alt_typ TEXT NOT NULL,
        menytext TEXT NOT NULL
    )
''')

# Ta bort eventuell befintlig data för vecka 1
cursor.execute("DELETE FROM veckomeny WHERE vecka = 1")

# Lägg till testdata för vecka 1
test_data = [
    (1, 'måndag', 'Alt1', 'Köttbullar med potatismos och lingonsylt'),
    (1, 'måndag', 'Alt2', 'Vegetarisk lasagne med sallad'),
    (1, 'tisdag', 'Alt1', 'Fiskgratäng med kokt potatis'),
    (1, 'tisdag', 'Alt2', 'Kikärtscurry med ris'),
    (1, 'onsdag', 'Alt1', 'Kyckling med ris och grönsaker'),
    (1, 'onsdag', 'Alt2', 'Pastasallad med tomat och mozzarella'),
]

for data in test_data:
    cursor.execute("INSERT INTO veckomeny (vecka, dag, alt_typ, menytext) VALUES (?, ?, ?, ?)", data)

# Spara ändringar
conn.commit()

# Kontrollera att data sparades
cursor.execute("SELECT * FROM veckomeny WHERE vecka = 1")
rows = cursor.fetchall()
print(f"Lagt till {len(rows)} menyrader för vecka 1:")
for row in rows:
    print(f"  {row}")

conn.close()
print("\nTestdata tillagd! Gå till vecka 1 i personalvyn för att testa.")
