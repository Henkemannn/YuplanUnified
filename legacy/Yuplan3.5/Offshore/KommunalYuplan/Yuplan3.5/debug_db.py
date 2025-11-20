# Copyright (c) 2025 Henrik Jonsson, Yuplan. All rights reserved.
# Proprietary and confidential. Unauthorized copying, distribution or use is strictly prohibited.
import sqlite3

conn = sqlite3.connect('kost.db')
cursor = conn.cursor()

# Kontrollera om tabellen finns
try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='veckomeny'")
    table_exists = cursor.fetchone()
    print(f"Tabellen 'veckomeny' finns: {table_exists is not None}")
    
    if table_exists:
        # Visa schema
        cursor.execute("PRAGMA table_info(veckomeny)")
        schema = cursor.fetchall()
        print("Schema:", schema)
        
        # Visa data för vecka 1
        cursor.execute("SELECT * FROM veckomeny WHERE vecka = 1")
        rows = cursor.fetchall()
        print(f"Antal rader för vecka 1: {len(rows)}")
        for row in rows:
            print(f"  {row}")
    else:
        print("Tabellen finns inte - skapar den nu...")
        cursor.execute('''
            CREATE TABLE veckomeny (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vecka INTEGER NOT NULL,
                dag TEXT NOT NULL,
                alt_typ TEXT NOT NULL,
                menytext TEXT NOT NULL
            )
        ''')
        
        # Lägg till testdata
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
        
        conn.commit()
        print(f"Skapade tabellen och lade till {len(test_data)} testrader")

except Exception as e:
    print(f"Fel: {e}")

conn.close()
