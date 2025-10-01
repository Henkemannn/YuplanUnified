# Copyright (c) 2025 Henrik Jonsson, Yuplan. All rights reserved.
# Proprietary and confidential. Unauthorized copying, distribution or use is strictly prohibited.
import os
import sqlite3

DB_PATH = "kost.db"

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("🗑️ Gamla kost.db raderad.")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE admin_password (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        password_hash TEXT NOT NULL
    )
""")
cursor.execute("""
    CREATE TABLE avdelningar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        namn TEXT NOT NULL,
        boende_antal INTEGER NOT NULL,
        faktaruta TEXT
    )
""")
cursor.execute("""
    CREATE TABLE kosttyper (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        namn TEXT NOT NULL,
        formarkeras BOOLEAN NOT NULL DEFAULT 0
    )
""")
cursor.execute("""
    CREATE TABLE registreringar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vecka INTEGER NOT NULL,
        dag TEXT NOT NULL,
        maltid TEXT NOT NULL,
        avdelning_id INTEGER,
        kosttyp_id INTEGER,
        markerad BOOLEAN NOT NULL DEFAULT 0,
        UNIQUE (vecka, dag, maltid, avdelning_id, kosttyp_id),
        FOREIGN KEY (avdelning_id) REFERENCES avdelningar(id),
        FOREIGN KEY (kosttyp_id) REFERENCES kosttyper(id)
    )
""")
cursor.execute("""
    CREATE TABLE avdelning_kosttyp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        avdelning_id INTEGER NOT NULL,
        kosttyp_id INTEGER NOT NULL,
        antal INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (avdelning_id) REFERENCES avdelningar(id),
        FOREIGN KEY (kosttyp_id) REFERENCES kosttyper(id)
    )
""")
cursor.execute("""
    CREATE TABLE alt2_markering (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vecka INTEGER NOT NULL,
        avdelning_id INTEGER NOT NULL,
        dag TEXT NOT NULL,
        FOREIGN KEY (avdelning_id) REFERENCES avdelningar(id)
    )
""")
cursor.execute("""
    CREATE TABLE boende_antal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        avdelning_id INTEGER NOT NULL,
        dag TEXT NOT NULL,
        maltid TEXT NOT NULL,
        antal INTEGER NOT NULL,
        vecka INTEGER NOT NULL,
        FOREIGN KEY (avdelning_id) REFERENCES avdelningar(id)
    )
""")
cursor.execute("""
    CREATE TABLE veckomeny (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vecka INTEGER NOT NULL,
        dag TEXT NOT NULL,
        alt_typ TEXT NOT NULL,
        menytext TEXT NOT NULL
    )
""")

conn.commit()
conn.close()
print("✅ Ny kost.db skapad och alla tabeller är nu på plats!")
