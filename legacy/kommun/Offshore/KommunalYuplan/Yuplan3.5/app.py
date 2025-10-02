# Copyright (c) 2025 Henrik Jonsson, Yuplan. All rights reserved.
# Proprietary and confidential. Unauthorized copying, distribution or use is strictly prohibited.
print("START AV APPEN")
import io
import os
import sqlite3

# Sätt rätt sökväg till templates och static, oavsett om .py eller .exe
import sys
from shutil import copy2, copytree

import openpyxl
from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

# Hantera PyInstaller runtime-path (_MEIPASS) med säker fallback för typer och skapa persistent lagring
if getattr(sys, "frozen", False):  # körd som kompilerad exe
    _runtime_dir = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))  # inbakat innehåll
    # Mapp där exe ligger (persistent skrivbar plats för db/uploads)
    exe_dir = os.path.dirname(sys.executable)
    basedir = _runtime_dir  # templates/static hämtas från inbakat läge

    # Persistent DB-path bredvid exe
    external_db_path = os.path.join(exe_dir, "kost.db")
    if not os.path.exists(external_db_path):
        embedded_db = os.path.join(_runtime_dir, "kost.db")
        if os.path.exists(embedded_db):
            try:
                copy2(embedded_db, external_db_path)
                print(f"[INIT] Kopierade inbäddad kost.db till {external_db_path}")
            except Exception as e:
                print(f"[INIT][VARNING] Kunde inte kopiera kost.db: {e}")
    DB_PATH = external_db_path

    # Hantera uploads-mapp: skapa persistent variant och kopiera initialt innehåll om saknas
    embedded_uploads = os.path.join(_runtime_dir, "uploads")
    external_uploads = os.path.join(exe_dir, "uploads")
    if not os.path.isdir(external_uploads):
        try:
            if os.path.isdir(embedded_uploads):
                copytree(embedded_uploads, external_uploads)
                print(f"[INIT] Kopierade uploads till {external_uploads}")
            else:
                os.makedirs(external_uploads, exist_ok=True)
                print(f"[INIT] Skapade tom uploads {external_uploads}")
        except Exception as e:
            print(f"[INIT][VARNING] Kunde inte initiera uploads: {e}")
    persistent_upload_folder = external_uploads
else:  # körd som vanlig .py
    basedir = os.path.abspath(os.path.dirname(__file__))
    DB_PATH = "kost.db"
    persistent_upload_folder = "uploads"

app = Flask(
    __name__,
    template_folder=os.path.join(basedir, "templates"),
    static_folder=os.path.join(basedir, "static")
)
app.secret_key = "superhemligt"

_tmpl_folder = app.template_folder or ""  # försäkra str för typer
print("TEMPLATE FOLDER:", _tmpl_folder)
print("Finns index.html?", os.path.exists(os.path.join(_tmpl_folder, "index.html")))
print("STATIC FOLDER:", app.static_folder or "")

# --- Exportera rapport till Excel ---
def ensure_database():
    """Skapa databas och tabeller om de inte finns.
    Körs vid uppstart så att en tom distribution kan starta direkt.
    """
    schema_statements = [
        """CREATE TABLE IF NOT EXISTS avdelningar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            namn TEXT NOT NULL,
            boende_antal INTEGER DEFAULT 0,
            faktaruta TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS kosttyper (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            namn TEXT NOT NULL,
            formarkeras INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS avdelning_kosttyp (
            avdelning_id INTEGER NOT NULL,
            kosttyp_id INTEGER NOT NULL,
            antal INTEGER DEFAULT 1,
            PRIMARY KEY (avdelning_id, kosttyp_id)
        )""",
        """CREATE TABLE IF NOT EXISTS registreringar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vecka INTEGER NOT NULL,
            dag TEXT NOT NULL,
            maltid TEXT NOT NULL,
            avdelning_id INTEGER NOT NULL,
            kosttyp_id INTEGER NOT NULL,
            markerad INTEGER DEFAULT 0,
            UNIQUE(vecka, dag, maltid, avdelning_id, kosttyp_id)
        )""",
        """CREATE TABLE IF NOT EXISTS boende_antal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            avdelning_id INTEGER NOT NULL,
            dag TEXT NOT NULL,
            maltid TEXT NOT NULL,
            antal INTEGER DEFAULT 0,
            vecka INTEGER NOT NULL,
            UNIQUE(avdelning_id, dag, maltid, vecka)
        )""",
        """CREATE TABLE IF NOT EXISTS alt2_markering (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            avdelning_id INTEGER NOT NULL,
            dag TEXT NOT NULL,
            vecka INTEGER NOT NULL,
            UNIQUE(avdelning_id, dag, vecka)
        )""",
        """CREATE TABLE IF NOT EXISTS veckomeny (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vecka INTEGER NOT NULL,
            dag TEXT NOT NULL,
            alt_typ TEXT NOT NULL,
            menytext TEXT,
            UNIQUE(vecka, dag, alt_typ)
        )"""
    ]
    try:
        ny_db = not os.path.exists(DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for stmt in schema_statements:
            cur.execute(stmt)
        conn.commit()
        conn.close()
        if ny_db:
            print(f"[INIT] Skapade ny databas och tabeller i {DB_PATH}")
    except Exception as e:
        print(f"[INIT][FEL] Kunde inte initiera databas: {e}")

# Kör init direkt efter att DB_PATH definierats
ensure_database()
@app.route("/export_rapport", methods=["POST"])
def export_rapport():
    print("/export_rapport route called")
    vecka = request.form.get("vecka")
    avdelning = request.form.get("avdelning")
    vytyp = request.form.get("vytyp", "dag")

    # Återanvänd rapportlogik
    with app.test_request_context("/rapport", method="POST", data=request.form):
        resp = rapport()
        # summerat_resultat, vytyp, avdelningar, vecka_vald, avdelning_vald finns i context
        # Men vi måste köra logiken igen för att få summerat_resultat
    conn = get_db_connection()
    avdelningar = conn.execute("SELECT id, namn, boende_antal FROM avdelningar").fetchall()
    vecka_boende_map = {}
    for avd in avdelningar:
        rows = conn.execute("SELECT antal FROM boende_antal WHERE avdelning_id = ? AND vecka = ?", (avd["id"], vecka or 1)).fetchall()
        per_day_antal = [row["antal"] for row in rows]
        varierat = False
        if len(per_day_antal) > 0:
            unique_antal = set(per_day_antal)
            if len(unique_antal) > 1:
                varierat = True
        vecka_boende_map[avd["id"]] = {"varierat": varierat, "per_day_antal": per_day_antal}
    daglista = ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]
    summerat_resultat = []
    # ...Kopiera rapportlogik från rapport() här, men spara summerat_resultat...
    # (För enkelhet, importera och återanvänd logik om möjligt, annars kopiera hit)
    # --- KORTAD: Här ska summerat_resultat fyllas på samma sätt som i rapport() ---
    # --- Förenklad: Kör rapport() och hämta summerat_resultat från context ---
    # Men Flask har ingen enkel context-sharing, så vi kör logiken igen (eller extrahera till hjälpfunktion vid behov)
    # --- KORTAD: Här ---
    # (För demo, exportera en tom fil om summerat_resultat är tom)

    # --- Rapportlogik (samma som i rapport()) ---
    vecka_vald = vecka
    avdelning_vald = avdelning
    summerat_resultat = []
    # Hämta data och bygg summerat_resultat (samma kod som i rapport())
    alla_reg = conn.execute("""
        SELECT avdelning_id, dag, maltid, kosttyp_id, markerad
        FROM registreringar
        WHERE vecka = ?
    """, (vecka_vald,)).fetchall()
    boende = conn.execute("""
        SELECT avdelning_id, dag, maltid, antal
        FROM boende_antal
        WHERE vecka = ?
    """, (vecka_vald,)).fetchall()
    kopplingar = conn.execute("""
        SELECT avdelning_id, kosttyp_id, antal
        FROM avdelning_kosttyp
    """).fetchall()
    formarkerade_kosttyper = conn.execute("""
        SELECT id FROM kosttyper WHERE formarkeras = 1
    """).fetchall()
    alt2_rows = conn.execute("""
        SELECT avdelning_id, dag FROM alt2_markering WHERE vecka = ?
    """, (vecka_vald,)).fetchall()
    conn.close()

    boende_map = {(b["avdelning_id"], b["dag"], b["maltid"]): b["antal"] for b in boende}
    kopplingar_map = {(k["avdelning_id"], k["kosttyp_id"]): k["antal"] for k in kopplingar}
    formarkerade_ids = {row["id"] for row in formarkerade_kosttyper}
    alt2_map = {(row["avdelning_id"], row["dag"]) for row in alt2_rows}
    reg_map = {(r["avdelning_id"], r["dag"], r["maltid"], r["kosttyp_id"]): r["markerad"] for r in alla_reg}
    markerad_map = {}
    for key, val in reg_map.items():
        avd_id, dag, maltid, kosttyp_id = key
        if val == 1 and (avd_id, kosttyp_id) in kopplingar_map:
            markerad_map[key] = True
    for avd in avdelningar:
        for dag in daglista:
            for maltid in ["Lunch", "Kväll"]:
                for kosttyp_id in formarkerade_ids:
                    if (avd["id"], kosttyp_id) in kopplingar_map:
                        key = (avd["id"], dag, maltid, kosttyp_id)
                        if key not in reg_map:
                            markerad_map[key] = True

    for avd in avdelningar:
        if avdelning_vald != "alla" and avdelning_vald and str(avd["id"]) != avdelning_vald:
            continue
        avd_rader = []
        sum_lunch_normal = 0
        sum_lunch_special = 0
        sum_kvall_normal = 0
        sum_kvall_special = 0
        for dag in daglista:
            rad = {
                "avdelning": avd["namn"],
                "dag": dag,
                "boende": None,
                "boende_lunch": None,
                "boende_kvall": None,
                "lunch_normal": 0,
                "lunch_special": 0,
                "kvall_normal": 0,
                "kvall_special": 0
            }
            for maltid in ["Lunch", "Kväll"]:
                boendeantal = boende_map.get((avd["id"], dag, maltid))
                if boendeantal is None:
                    if vecka_boende_map[avd["id"]]["per_day_antal"]:
                        boendeantal = vecka_boende_map[avd["id"]]["per_day_antal"][0]
                    else:
                        boendeantal = avd["boende_antal"] or 0
                if maltid == "Lunch":
                    rad["boende_lunch"] = boendeantal
                else:
                    rad["boende_kvall"] = boendeantal
                if rad["boende"] is None:
                    rad["boende"] = "varierat" if vecka_boende_map[avd["id"]]["varierat"] else boendeantal
                special = 0
                for (a_id, d, m, kost_id), is_marked in markerad_map.items():
                    if a_id == avd["id"] and d == dag and m == maltid and is_marked:
                        special += kopplingar_map.get((avd["id"], kost_id), 1)
                normalkost = boendeantal - special
                if maltid == "Lunch":
                    rad["lunch_special"] = special
                    rad["lunch_normal"] = normalkost
                    sum_lunch_special += special
                    sum_lunch_normal += normalkost
                else:
                    rad["kvall_special"] = special
                    rad["kvall_normal"] = normalkost
                    sum_kvall_special += special
                    sum_kvall_normal += normalkost
            avd_rader.append(rad)
        if vytyp == "dag":
            for i, rad in enumerate(avd_rader):
                if i > 0:
                    rad["avdelning"] = ""
                summerat_resultat.append(rad)
            summerat_resultat.append({
                "avdelning": avd["namn"] + " (SUMMA)",
                "dag": "",
                "boende": "",
                "boende_lunch": "",
                "boende_kvall": "",
                "lunch_normal": sum_lunch_normal,
                "lunch_special": sum_lunch_special,
                "kvall_normal": sum_kvall_normal,
                "kvall_special": sum_kvall_special
            })
        elif vytyp == "vecka":
            summerat_resultat.append({
                "avdelning": avd["namn"],
                "dag": "SUMMA",
                "boende": "",
                "lunch_normal": sum_lunch_normal,
                "lunch_special": sum_lunch_special,
                "kvall_normal": sum_kvall_normal,
                "kvall_special": sum_kvall_special
            })

    # Skapa Excel-fil
    wb = openpyxl.Workbook()
    # wb.active returnerar Worksheet; typkontrollen verkar tro None – hjälp Pylance med explicit typning
    from typing import cast
    ws = cast("openpyxl.worksheet.worksheet.Worksheet", wb.active)  # type: ignore
    ws.title = "Rapport"
    # Sätt rubriker
    if vytyp == "dag":
        ws.append(["Avdelning", "Veckodag", "Boende Lunch", "Boende Kväll", "Lunch – Special", "Lunch – Normal", "Kväll – Special", "Kväll – Normal"])
        for rad in summerat_resultat:
            ws.append([
                rad.get("avdelning", ""),
                rad.get("dag", ""),
                rad.get("boende_lunch", ""),
                rad.get("boende_kvall", ""),
                rad.get("lunch_special", ""),
                rad.get("lunch_normal", ""),
                rad.get("kvall_special", ""),
                rad.get("kvall_normal", "")
            ])
    else:
        ws.append(["Avdelning", "Veckodag", "Boende", "Lunch – Special", "Lunch – Normal", "Kväll – Special", "Kväll – Normal"])
        for rad in summerat_resultat:
            ws.append([
                rad.get("avdelning", ""),
                rad.get("dag", ""),
                rad.get("boende", ""),
                rad.get("lunch_special", ""),
                rad.get("lunch_normal", ""),
                rad.get("kvall_special", ""),
                rad.get("kvall_normal", "")
            ])
    # Spara till bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filnamn = f"RapportVecka{vecka}.xlsx"
    return send_file(output, as_attachment=True, download_name=filnamn, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")



# Lägg till globala template-variabler
@app.context_processor
def inject_global_vars():
    return {
        # datetime imported as class; use directly
        "current_year": datetime.now().year
    }

# Konfiguration för filuppladdning
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"docx", "doc"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

"""Konfigurera uppladdningsmapp.
Om vi kör fryst exe används persistent_upload_folder (bredvid exe),
annars standard 'uploads'."""
if getattr(sys, "frozen", False):
    app.config["UPLOAD_FOLDER"] = persistent_upload_folder
else:
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------- AVDELNING LOGIN ----------
@app.route("/avdelning_login", methods=["GET", "POST"])
def avdelning_login():
    # Enkel inloggningsvy för avdelning, kan byggas ut vid behov
    if request.method == "POST":
        anvandarnamn = request.form.get("anvandarnamn")
        losenord = request.form.get("losenord")
        conn = get_db_connection()
        row = conn.execute("SELECT id, namn, losenord_hash FROM avdelningar WHERE anvandarnamn = ?", (anvandarnamn,)).fetchone()
        conn.close()
        if row and losenord:
            from werkzeug.security import check_password_hash
            if check_password_hash(row["losenord_hash"], losenord):
                session["avdelning_id"] = row["id"]
                session["avdelning_namn"] = row["namn"]
                return redirect(url_for("menyval"))
        fel = "Fel användarnamn eller lösenord."
        return render_template("avdelning_login.html", fel=fel)
    return render_template("avdelning_login.html")

# ----------- MENYVAL (PERSONALVY) ----------
@app.route("/menyval", methods=["GET", "POST"])
def menyval():
    if not session.get("avdelning_id"):
        return redirect(url_for("avdelning_login"))
    vecka = request.args.get("vecka", default=datetime.date.today().isocalendar()[1], type=int)
    avdelning_id = session["avdelning_id"]
    conn = get_db_connection()
    dagar = ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]

    # Spara val om POST
    sparat_meddelande = None
    vecka_klar = False
    if request.method == "POST":
        vecka = int(request.form.get("vecka", vecka))
        conn.execute("DELETE FROM alt2_markering WHERE vecka = ? AND avdelning_id = ?", (vecka, avdelning_id))
        valda_dagar = 0
        for dag in dagar:
            val = request.form.get(f"val_{dag}")
            if val == "Alt2":
                conn.execute("INSERT INTO alt2_markering (vecka, avdelning_id, dag) VALUES (?, ?, ?)", (vecka, avdelning_id, dag))
                valda_dagar += 1
        conn.commit()
        sparat_meddelande = "Dina val har sparats."
        if valda_dagar == 7:
            vecka_klar = True


    # Hämta alla veckor från både menytext och alt2_markering
    veckor_meny_rows = conn.execute("SELECT DISTINCT vecka FROM veckomeny").fetchall()
    veckor_markering_rows = conn.execute("SELECT DISTINCT vecka FROM alt2_markering WHERE avdelning_id = ?", (avdelning_id,)).fetchall()
    veckor_set = set(row["vecka"] for row in veckor_meny_rows) | set(row["vecka"] for row in veckor_markering_rows)
    veckor = sorted(list(veckor_set))
    # Lägg till aktuell vecka om den inte finns
    if vecka not in veckor:
        veckor.append(vecka)
        veckor = sorted(list(set(veckor)))
    veckostatus = []
    for v in veckor:
        # Hämta markerade dagar (Alt2)
        alt2_rows = conn.execute("SELECT dag FROM alt2_markering WHERE vecka = ? AND avdelning_id = ?", (v, avdelning_id)).fetchall()
        alt2_markerade = {row["dag"] for row in alt2_rows}
        # Hämta menytext för veckan
        meny_rows = conn.execute("SELECT dag FROM veckomeny WHERE vecka = ?", (v,)).fetchall()
        dagar_med_meny = {row["dag"] for row in meny_rows}
        dagar = ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]
        # Kontroll: har användaren gjort något val för veckan? (dvs. finns det poster i alt2_markering för veckan/avdelning ELLER har POST skett för veckan)
        # Om det inte finns någon post i alt2_markering för veckan/avdelning, visa alltid 'Ej färdigvalda'
        if len(alt2_markerade) == 0:
            status = "Ej färdigvalda"
            markerade = set()
        else:
            # Om det finns menytext för veckan, kolla om det finns val för alla dagar (Alt2 eller Alt1)
            valda_dagar = set()
            for dag in dagar:
                if dag in alt2_markerade or dag in dagar_med_meny:
                    valda_dagar.add(dag)
            status = "Färdigvalda" if len(valda_dagar) == 7 else "Ej färdigvalda"
            markerade = valda_dagar
        veckostatus.append({"vecka": v, "status": status, "markerade": markerade})

    # Hämta markerade dagar för Alt2 denna vecka
    alt2_rows = conn.execute("SELECT dag FROM alt2_markering WHERE vecka = ? AND avdelning_id = ?", (vecka, avdelning_id)).fetchall()
    markerade = {row["dag"] for row in alt2_rows}
    # Hämta menytext för aktuell vecka, både Alt1 och Alt2
    meny_rows = conn.execute("SELECT dag, alt_typ, menytext FROM veckomeny WHERE vecka = ?", (vecka,)).fetchall()
    meny_map = {f"{row['dag']}_{row['alt_typ']}": row["menytext"] for row in meny_rows}
    # Veckolista: visa status och menytext för varje dag
    veckodata = []
    for dag in dagar:
        veckodata.append({
            "dag": dag,
            "markerad": dag in markerade,
            "menytext_alt1": meny_map.get(f"{dag}_Alt1", ""),
            "menytext_alt2": meny_map.get(f"{dag}_Alt2", ""),
            "menytext_dessert": meny_map.get(f"{dag}_Dessert", ""),
            "menytext_kvall": meny_map.get(f"{dag}_Kväll", "")
        })
    conn.close()
    return render_template("menyval.html", vecka=vecka, veckodata=veckodata, avdelning_namn=session.get("avdelning_namn"), veckostatus=veckostatus, sparat_meddelande=sparat_meddelande, vecka_klar=vecka_klar, visa_menybar=False)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrera_databas():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Lista över kolumner vi vill säkerställa finns i 'registreringar'
    cursor.execute("PRAGMA table_info(registreringar)")
    kolumner = [rad["name"] for rad in cursor.fetchall()]

    if "vecka" not in kolumner:
        print("➕ Lägger till kolumn 'vecka' i tabellen 'registreringar'...")
        cursor.execute("ALTER TABLE registreringar ADD COLUMN vecka INTEGER DEFAULT 1")

    # Lägg till fler migrationskontroller här vid behov
    # --- Migrationssteg för avdelningar: loginfält ---
    cursor.execute("PRAGMA table_info(avdelningar)")
    avd_kolumner = [rad["name"] for rad in cursor.fetchall()]
    if "anvandarnamn" not in avd_kolumner:
        print("\u2795 Lägger till kolumn 'anvandarnamn' i tabellen 'avdelningar'...")
        cursor.execute("ALTER TABLE avdelningar ADD COLUMN anvandarnamn TEXT")
        # Skapa unikt index om det inte redan finns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_avdelningar_anvandarnamn_unique'")
        if not cursor.fetchone():
            print("\u2795 Skapar unikt index på 'anvandarnamn'...")
            cursor.execute("CREATE UNIQUE INDEX idx_avdelningar_anvandarnamn_unique ON avdelningar(anvandarnamn)")
    if "losenord_hash" not in avd_kolumner:
        print("\u2795 Lägger till kolumn 'losenord_hash' i tabellen 'avdelningar'...")
        cursor.execute("ALTER TABLE avdelningar ADD COLUMN losenord_hash TEXT")

    # --- Migrationssteg för veckomeny ---
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='veckomeny'")
    if not cursor.fetchone():
        print("\u2795 Skapar tabell 'veckomeny'...")
        cursor.execute("""
            CREATE TABLE veckomeny (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vecka INTEGER NOT NULL,
                dag TEXT NOT NULL,
                alt_typ TEXT NOT NULL,
                menytext TEXT NOT NULL
            )
        """)
    else:
        # Om tabellen finns, kontrollera om alt_typ finns
        cursor.execute("PRAGMA table_info(veckomeny)")
        veckomeny_kolumner = [rad["name"] for rad in cursor.fetchall()]
        if "alt_typ" not in veckomeny_kolumner:
            print("\u2795 Lägger till kolumn 'alt_typ' i tabellen 'veckomeny'...")
            cursor.execute("ALTER TABLE veckomeny ADD COLUMN alt_typ TEXT DEFAULT 'Alt1'")

    conn.commit()
    conn.close()

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("🗑️ Gamla kost.db raderad.")

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE admin_password (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                password_hash TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE avdelningar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namn TEXT NOT NULL,
                boende_antal INTEGER NOT NULL,
                faktaruta TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE kosttyper (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namn TEXT NOT NULL,
                formarkeras BOOLEAN NOT NULL DEFAULT 0
            )
        """)
        cur.execute("""
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
        cur.execute("""
            CREATE TABLE avdelning_kosttyp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                avdelning_id INTEGER NOT NULL,
                kosttyp_id INTEGER NOT NULL,
                antal INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (avdelning_id) REFERENCES avdelningar(id),
                FOREIGN KEY (kosttyp_id) REFERENCES kosttyper(id)
            )
        """)
        cur.execute("""
            CREATE TABLE alt2_markering (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vecka INTEGER NOT NULL,
                avdelning_id INTEGER NOT NULL,
                dag TEXT NOT NULL,
                FOREIGN KEY (avdelning_id) REFERENCES avdelningar(id)
            )
        """)
        cur.execute("""
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
        conn.commit()
        print("✅ Ny kost.db skapad och alla tabeller är nu på plats!")

def skapa_testdata():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Lägg till avdelningar
    cursor.execute("INSERT INTO avdelningar (namn, boende_antal, faktaruta) VALUES ('Solrosen', 10, '')")
    cursor.execute("INSERT INTO avdelningar (namn, boende_antal, faktaruta) VALUES ('Lönnen', 10, '')")

    # Lägg till kosttyper
    cursor.execute("INSERT INTO kosttyper (namn, formarkeras) VALUES ('Glutenfri', 0)")
    cursor.execute("INSERT INTO kosttyper (namn, formarkeras) VALUES ('Laktosfri', 0)")
    cursor.execute("INSERT INTO kosttyper (namn, formarkeras) VALUES ('Timbal', 1)")

    # Kopplingar
    cursor.execute("INSERT INTO avdelning_kosttyp (avdelning_id, kosttyp_id, antal) VALUES (1, 1, 2)")
    cursor.execute("INSERT INTO avdelning_kosttyp (avdelning_id, kosttyp_id, antal) VALUES (1, 3, 1)")
    cursor.execute("INSERT INTO avdelning_kosttyp (avdelning_id, kosttyp_id, antal) VALUES (2, 2, 1)")
    cursor.execute("INSERT INTO avdelning_kosttyp (avdelning_id, kosttyp_id, antal) VALUES (2, 3, 2)")

    # Registreringar – vecka 31, måndag lunch
    cursor.execute("""INSERT INTO registreringar (vecka, dag, maltid, avdelning_id, kosttyp_id, markerad)
                      VALUES (31, 'Mån', 'Lunch', 1, 1, 1)""")
    cursor.execute("""INSERT INTO registreringar (vecka, dag, maltid, avdelning_id, kosttyp_id, markerad)
                      VALUES (31, 'Mån', 'Lunch', 2, 2, 1)""")

    # Boendeantal
    for avd_id in [1, 2]:
        cursor.execute("""INSERT INTO boende_antal (avdelning_id, dag, maltid, antal, vecka)
                          VALUES (?, 'Mån', 'Lunch', 10, 31)""", (avd_id,))

    conn.commit()
    conn.close()
    print("✅ Testdata skapad för vecka 31.")

migrera_databas()

# ✅ Kontrollera om kolumnen 'vecka' finns i registreringar
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(registreringar)")
kolumner = [rad["name"] for rad in cursor.fetchall()]
conn.close()

if "vecka" in kolumner:
    print("✅ Kolumnen 'vecka' finns i tabellen 'registreringar'.")
else:
    print("❌ Kolumnen 'vecka' saknas i tabellen 'registreringar'.")

# ----------- STARTSIDA ----------
@app.route("/")
def index():
    return render_template("index.html")


# ----------- ADMINLOGIN ----------
from werkzeug.security import check_password_hash, generate_password_hash


def get_admin_password_hash():
    conn = get_db_connection()
    row = conn.execute("SELECT password_hash FROM admin_password WHERE id=1").fetchone()
    conn.close()
    if row:
        return row["password_hash"]
    return None

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        pw = request.form.get("lösenord")
        hash_in_db = get_admin_password_hash()
        if hash_in_db and pw:
            if check_password_hash(hash_in_db, pw):  # pw är nu str
                session["admin"] = True
                return redirect(url_for("adminpanel"))
            else:
                return render_template("index.html", fel="Fel lösenord!")
        else:
            # Första gången: sätt lösenordet till det som anges
            if not pw:
                return render_template("index.html", fel="Lösenord saknas.")
            conn = get_db_connection()
            conn.execute("INSERT OR REPLACE INTO admin_password (id, password_hash) VALUES (1, ?)", (generate_password_hash(pw),))
            conn.commit()
            conn.close()
            session["admin"] = True
            return redirect(url_for("adminpanel"))
    return render_template("index.html")

# ----------- BYT LÖSENORD ----------
@app.route("/byt_losenord", methods=["POST"])
def byt_losenord():
    from werkzeug.security import check_password_hash, generate_password_hash
    nuvarande = request.form.get("nuvarande_losenord")
    nytt1 = request.form.get("nytt_losenord")
    nytt2 = request.form.get("nytt_losenord2")
    fel = None
    ok = None
    hash_in_db = get_admin_password_hash()
    if not nuvarande or not nytt1 or not nytt2:
        fel = "Du måste fylla i alla fält."
    elif not hash_in_db or not check_password_hash(hash_in_db, nuvarande):
        fel = "Nuvarande lösenord är felaktigt."
    elif nytt1 != nytt2:
        fel = "Lösenorden matchar inte."
    elif len(nytt1) < 4:
        fel = "Lösenordet måste vara minst 4 tecken."
    else:
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO admin_password (id, password_hash) VALUES (1, ?)", (generate_password_hash(nytt1),))
        conn.commit()
        conn.close()
        ok = "Lösenordet är nu uppdaterat!"
    return render_template("index.html", losenord_fel=fel, losenord_ok=ok)

# ----------- MENY- OCH AVDELNINGSADMINISTRERING ----------
@app.route("/meny_avdelning_admin", methods=["GET", "POST"])
def meny_avdelning_admin():
    if not session.get("admin"):
        return redirect(url_for("admin"))

    vecka = int(request.form.get("vecka_alt2", request.args.get("vecka", 1)))
    conn = get_db_connection()

    if request.method == "POST":
        # Hantera avdelningslogin
        if "spara_avd_login" in request.form:
            from werkzeug.security import generate_password_hash
            for avd_id in request.form.getlist("avd_login_id"):
                anvandarnamn = request.form.get(f"anvandarnamn_{avd_id}", "").strip()
                losenord = request.form.get(f"losenord_{avd_id}", "").strip()
                # Endast om användarnamn eller lösenord är ifyllt
                if anvandarnamn:
                    conn.execute("UPDATE avdelningar SET anvandarnamn = ? WHERE id = ?", (anvandarnamn, avd_id))
                if losenord:
                    hash = generate_password_hash(losenord)
                    conn.execute("UPDATE avdelningar SET losenord_hash = ? WHERE id = ?", (hash, avd_id))

        # Hantera menytext för vecka
        elif "spara_veckomeny" in request.form:
            vecka_meny = int(request.form.get("veckomeny_vecka", vecka))
            dagar = ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]
            for dag in dagar:
                for alt_typ in ["Alt1", "Alt2"]:
                    menytext = request.form.get(f"menytext_{dag}_{alt_typ}", "").strip()
                    # Ta bort ev. gammal menytext för dag/vecka/alt_typ
                    conn.execute("DELETE FROM veckomeny WHERE vecka = ? AND dag = ? AND alt_typ = ?", (vecka_meny, dag, alt_typ))
                    if menytext:
                        conn.execute("INSERT INTO veckomeny (vecka, dag, alt_typ, menytext) VALUES (?, ?, ?, ?)", (vecka_meny, dag, alt_typ, menytext))

        # Hantera Alt2-markeringar
        elif "spara_alt2" in request.form:
            vecka = int(request.form.get("vecka_alt2", vecka))
            conn.execute("DELETE FROM alt2_markering WHERE vecka = ?", (vecka,))
            for avd in conn.execute("SELECT id FROM avdelningar").fetchall():
                for dag in ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]:
                    fkey = f"alt2_{avd['id']}_{dag}"
                    if fkey in request.form:
                        conn.execute("INSERT INTO alt2_markering (avdelning_id, dag, vecka) VALUES (?, ?, ?)",
                                     (avd["id"], dag, vecka))

        conn.commit()

    # Hämta data för visning
    avdelningar = conn.execute("SELECT * FROM avdelningar").fetchall()
    alt2_rows = conn.execute("SELECT * FROM alt2_markering WHERE vecka = ?", (vecka,)).fetchall()
    veckomeny_rows = conn.execute("SELECT dag, alt_typ, menytext FROM veckomeny WHERE vecka = ?", (vecka,)).fetchall()

    alt2_map = {}
    for rad in alt2_rows:
        alt2_map.setdefault(rad["avdelning_id"], []).append(rad["dag"])

    veckomeny_map = {f"{row['dag']}_{row['alt_typ']}": row["menytext"] for row in veckomeny_rows}

    conn.close()
    return render_template("meny_avdelning_admin.html",
                           avdelningar=avdelningar,
                           alt2_markeringar=alt2_map,
                           valt_vecka=vecka,
                           veckomeny_map=veckomeny_map)

# ----------- ADMINPANEL ----------
@app.route("/adminpanel", methods=["GET", "POST"])
def adminpanel():
    if not session.get("admin"):
        return redirect(url_for("admin"))

    # Hämta vecka från GET först, sedan POST, annars dynamisk standard
    vecka = request.args.get("vecka", type=int)
    if vecka is None:
        vecka = request.form.get("vecka", type=int)
    if vecka is None:
        vecka = get_default_week()
    session["last_week"] = vecka

    conn = get_db_connection()

    if request.method == "POST":
        ändringar = False
        if "lägg_till_avd" in request.form:
            namn = request.form["avd_namn"]
            antal = int(request.form["boende_antal"])
            conn.execute("INSERT INTO avdelningar (namn, boende_antal) VALUES (?, ?)", (namn, antal))
            ändringar = True

        elif "lägg_till_kost" in request.form:
            namn = request.form["kost_namn"]
            formarkeras = 1 if "formarkeras" in request.form else 0
            conn.execute("INSERT INTO kosttyper (namn, formarkeras) VALUES (?, ?)", (namn, formarkeras))
            ändringar = True

        elif "spara_kopplingar" in request.form:
            conn.execute("DELETE FROM avdelning_kosttyp")
            valda = request.form.getlist("koppling")
            for val in valda:
                avd_id, kost_id = map(int, val.split("_"))
                antal_key = f"antal_{avd_id}_{kost_id}"
                try:
                    antal = int(request.form.get(antal_key, 1))
                except ValueError:
                    antal = 1
                conn.execute("INSERT INTO avdelning_kosttyp (avdelning_id, kosttyp_id, antal) VALUES (?, ?, ?)",
                             (avd_id, kost_id, antal))

            avdelningar_tmp = conn.execute("SELECT * FROM avdelningar").fetchall()
            for avd in avdelningar_tmp:
                fkey = f'faktaruta_{avd["id"]}'
                if fkey in request.form:
                    text = request.form[fkey]
                    conn.execute("UPDATE avdelningar SET faktaruta = ? WHERE id = ?", (text, avd["id"]))
            ändringar = True

        elif "radera_kosttyp" in request.form:
            kost_id = int(request.form["radera_kosttyp"])
            conn.execute("DELETE FROM avdelning_kosttyp WHERE kosttyp_id = ?", (kost_id,))
            conn.execute("DELETE FROM registreringar WHERE kosttyp_id = ?", (kost_id,))
            conn.execute("DELETE FROM kosttyper WHERE id = ?", (kost_id,))
            ändringar = True

        if ändringar:
            conn.commit()
            conn.close()
            # Post/Redirect/Get för att undvika dubbelpost och bevara vecka
            return redirect(url_for("adminpanel", vecka=vecka))

    # GET eller ingen ändring -> bygg vydata
    avdelningar = conn.execute("SELECT * FROM avdelningar").fetchall()
    kosttyper = conn.execute("SELECT * FROM kosttyper").fetchall()
    kopplingar = conn.execute("SELECT * FROM avdelning_kosttyp").fetchall()

    avd_kost_map = {}
    avd_antal_map = {}
    for rad in kopplingar:
        avd_kost_map.setdefault(rad["avdelning_id"], set()).add(rad["kosttyp_id"])
        avd_antal_map.setdefault(rad["avdelning_id"], {})[rad["kosttyp_id"]] = rad["antal"]

    avdelning_lista = []
    for avd in avdelningar:
        rows = conn.execute("SELECT dag, maltid, antal FROM boende_antal WHERE avdelning_id = ? AND vecka = ?", (avd["id"], vecka)).fetchall()
        per_day_antal = [row["antal"] for row in rows]
        inherited = False
        # Om inga poster denna vecka: sök bakåt efter senaste vecka med poster
        if not per_day_antal:
            prev_week = vecka - 1
            while prev_week >= 1 and not per_day_antal:
                prev_rows = conn.execute(
                    "SELECT dag, maltid, antal FROM boende_antal WHERE avdelning_id = ? AND vecka = ?",
                    (avd["id"], prev_week)
                ).fetchall()
                if prev_rows:
                    per_day_antal = [r["antal"] for r in prev_rows]
                    inherited = True
                    break
                prev_week -= 1
        varierat = False
        if per_day_antal:
            if len(set(per_day_antal)) > 1:
                varierat = True
        boende_val = "varierat" if varierat else (per_day_antal[0] if len(per_day_antal) == 1 else avd["boende_antal"])
        avdelning_lista.append({
            "id": avd["id"],
            "namn": avd["namn"],
            "boende_antal": boende_val,
            "faktaruta": avd["faktaruta"] or "",
            "kopplade_kosttyper": avd_kost_map.get(avd["id"], set()),
            "kopplade_antal": avd_antal_map.get(avd["id"], {}),
        })

    conn.close()
    return render_template("adminpanel.html",
                           avdelningar=avdelning_lista,
                           kosttyper=kosttyper,
                           valt_vecka=vecka)
# ----------- PERSONALVY ----------
from datetime import datetime


def get_default_week():
    """Return the default week number to show.
    Priority:
      1. session['last_week'] if present
      2. current ISO week number
    Falls back to 1 only if everything else fails (should not normally happen).
    """
    try:
        if "last_week" in session:
            return int(session["last_week"])
        # datetime.isocalendar().week for Python 3.11+
        return datetime.now().isocalendar().week
    except Exception:
        return 1

@app.route("/veckovy")
def veckovy():
    # Use provided vecka if in query, else dynamic default
    vecka = request.args.get("vecka", type=int)
    if vecka is None:
        vecka = get_default_week()
    # Store chosen week in session for subsequent views
    session["last_week"] = vecka
    conn = get_db_connection()

    avdelningar = conn.execute("SELECT * FROM avdelningar").fetchall()
    kosttyper = conn.execute("SELECT * FROM kosttyper").fetchall()
    kopplingar = conn.execute("SELECT * FROM avdelning_kosttyp").fetchall()
    registreringar = conn.execute("SELECT * FROM registreringar WHERE vecka = ?", (vecka,)).fetchall()
    alt2_rows = conn.execute("SELECT * FROM alt2_markering WHERE vecka = ?", (vecka,)).fetchall()

    koppling_dict = {}
    for k in kopplingar:
        koppling_dict.setdefault(k["avdelning_id"], {})[k["kosttyp_id"]] = k["antal"]

    reg_dict = {(r["avdelning_id"], r["kosttyp_id"], r["dag"], r["maltid"]): r["markerad"] for r in registreringar}

    alt2_map = {}
    for rad in alt2_rows:
        alt2_map.setdefault(rad["avdelning_id"], set()).add(rad["dag"])

    data = []
    for avd in avdelningar:
        kostlista = []
        for kost in kosttyper:
            if koppling_dict.get(avd["id"], {}).get(kost["id"]) is None:
                continue
            antal = koppling_dict[avd["id"]][kost["id"]]
            celler = []
            for dag in ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]:
                for maltid in ["Lunch", "Kväll"]:
                    nyckel = (avd["id"], kost["id"], dag, maltid)
                    markerad = reg_dict.get(nyckel, kost["formarkeras"] == 1)
                    alt2_gul = (maltid == "Lunch" and dag in alt2_map.get(avd["id"], set()))
                    cell = {
                        "dag": dag,
                        "maltid": maltid,
                        "markerad": markerad,
                        "avdelning_id": avd["id"],
                        "kosttyp_id": kost["id"],
                        "antal": antal,
                        "alt2_gul": alt2_gul
                    }
                    celler.append(cell)
            kostlista.append({"namn": kost["namn"], "celler": celler})

        antal_boende_per_dag = {}
        boende_rows = conn.execute(
            "SELECT dag, maltid, antal FROM boende_antal WHERE avdelning_id = ? AND vecka = ?",
            (avd["id"], vecka)
        ).fetchall()
        boende_map = {(row["dag"], row["maltid"]): row["antal"] for row in boende_rows}
        boende_antal_list = []
        for dag in ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]:
            for maltid in ["Lunch", "Kväll"]:
                antal = boende_map.get((dag, maltid), avd["boende_antal"])
                alt2_gul = (maltid == "Lunch" and dag in alt2_map.get(avd["id"], set()))
                antal_boende_per_dag[(dag, maltid)] = (antal, alt2_gul)
                boende_antal_list.append(antal)
        varierat = len(set([a for a in boende_antal_list if a is not None])) > 1
        data.append({
            "id": avd["id"],
            "namn": avd["namn"],
            "faktaruta": avd["faktaruta"],
            "kosttyper": kostlista,
            "antal_boende_per_dag": antal_boende_per_dag,
            "varierat_boende": varierat
        })

    # Hämta menydata för popup-visning
    meny_rows = conn.execute("SELECT dag, alt_typ, menytext FROM veckomeny WHERE vecka = ?", (vecka,)).fetchall()
    meny_data = {}
    
    for row in meny_rows:
        dag = str(row["dag"]).lower() if row["dag"] else None
        if dag and dag not in meny_data:
            meny_data[dag] = {}
        # Make sure we only store string values and handle Alt1/Alt2 correctly
        alt_typ = str(row["alt_typ"]).lower() if row["alt_typ"] else None
        menytext = str(row["menytext"]) if row["menytext"] else None
        if dag and alt_typ and menytext:
            meny_data[dag][alt_typ] = menytext

    # TEMPORÄR DEMO-DATA för vecka 1 om ingen data finns
    if not meny_data and vecka == 1:
        meny_data = {
            "måndag": {
                "alt1": "Köttbullar med potatismos och lingonsylt",
                "alt2": "Vegetarisk lasagne med sallad"
            },
            "tisdag": {
                "alt1": "Fiskgratäng med kokt potatis",
                "alt2": "Kikärtscurry med ris"
            },
            "onsdag": {
                "alt1": "Kyckling med ris och grönsaker",
                "alt2": "Pastasallad med tomat och mozzarella"
            }
        }

    # Ensure meny_data is never None or contains undefined values
    if not meny_data:
        meny_data = {}

    conn.close()
    return render_template("veckovy.html", vecka=vecka, data=data, alt2_markeringar=alt2_map, kosttyper=kosttyper, meny_data=meny_data)

# ----------- REDIGERA BOENDE ----------
@app.route("/redigera_boende/<int:avdelning_id>", methods=["GET", "POST"])
def redigera_boende(avdelning_id):
    vecka = request.args.get("vecka", type=int)
    if vecka is None:
        vecka = get_default_week()
    session["last_week"] = vecka
    conn = get_db_connection()
    dagar = ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]
    maltider = ["Lunch", "Kväll"]

    if request.method == "POST":
        totalantal_raw = request.form.get("totalantal")
        conn.execute("DELETE FROM boende_antal WHERE avdelning_id = ? AND vecka = ?", (avdelning_id, vecka))

        if totalantal_raw and totalantal_raw.strip() != "":
            totalantal = int(totalantal_raw)
            conn.execute("UPDATE avdelningar SET boende_antal = ? WHERE id = ?", (totalantal, avdelning_id))
            for dag in dagar:
                for maltid in maltider:
                    conn.execute(
                        "INSERT INTO boende_antal (avdelning_id, dag, maltid, antal, vecka) VALUES (?, ?, ?, ?, ?)",
                        (avdelning_id, dag, maltid, totalantal, vecka)
                    )
        else:
            for dag in dagar:
                for maltid in maltider:
                    antal = int(request.form.get(f"{dag}_{maltid}", 0))
                    conn.execute(
                        "INSERT INTO boende_antal (avdelning_id, dag, maltid, antal, vecka) VALUES (?, ?, ?, ?, ?)",
                        (avdelning_id, dag, maltid, antal, vecka)
                    )
            # Viktigt: NOLLSTÄLL INTE det globala boende_antal här.
            # Tidigare sattes avdelningar.boende_antal = 0 när man sparade varierade värden för en vecka.
            # Det gjorde att framtida veckor (utan overrides) visade 0. Vi behåller nu befintligt globalt värde.

            # Framåt-propagation: kopiera detta varierade mönster till alla framtida veckor som saknar egna poster
            # (Veckor som redan har poster lämnas orörda)
            pattern_map = {}
            for dag in dagar:
                for maltid in maltider:
                    try:
                        pattern_map[(dag, maltid)] = int(request.form.get(f"{dag}_{maltid}", 0))
                    except (TypeError, ValueError):
                        pattern_map[(dag, maltid)] = 0
            for future_week in range(vecka + 1, 53):
                existing = conn.execute(
                    "SELECT 1 FROM boende_antal WHERE avdelning_id = ? AND vecka = ? LIMIT 1",
                    (avdelning_id, future_week)
                ).fetchone()
                if existing:
                    continue  # redan manuellt satt eller tidigare propagation
                # infoga mönster
                for (dag, maltid), antal_v in pattern_map.items():
                    conn.execute(
                        "INSERT INTO boende_antal (avdelning_id, dag, maltid, antal, vecka) VALUES (?, ?, ?, ?, ?)",
                        (avdelning_id, dag, maltid, antal_v, future_week)
                    )

        conn.commit()
        conn.close()
        return redirect(url_for("adminpanel", vecka=vecka))

    rows = conn.execute(
        "SELECT dag, maltid, antal FROM boende_antal WHERE avdelning_id = ? AND vecka = ?", (avdelning_id, vecka)
    ).fetchall()
    antal_map = {(row["dag"], row["maltid"]): row["antal"] for row in rows}

    # Bestäm om veckan är 'varierat' (mer än ett unikt värde) eller om alla värden är samma
    is_varierat = False
    if antal_map:
        värden = list(antal_map.values())
        unika = set(värden)
        if len(unika) > 1:
            is_varierat = True
        else:
            # Om exakt ett värde och det matchar globalt totalantal betraktas det som "fast"
            pass

    avd_row = conn.execute(
        "SELECT namn, boende_antal FROM avdelningar WHERE id = ?", (avdelning_id,)
    ).fetchone()

    conn.close()
    return render_template(
        "redigera_boende.html",
        avdelning_id=avdelning_id,
        avdelning_namn=avd_row["namn"],
        nuvarande_total=avd_row["boende_antal"],
        dagar=dagar,
        maltider=maltider,
        antal_map=antal_map,
        valt_vecka=vecka,
        is_varierat=is_varierat
    )

# ----------- PLANERA ----------
# ----------- PLANERA ----------
# ----------- PLANERA ----------
@app.route("/planera/<int:vecka>", methods=["GET", "POST"])
def planera(vecka):
    conn = get_db_connection()

    anrattning = None


    kosttyper = conn.execute("SELECT * FROM kosttyper").fetchall()
    avdelningar = conn.execute("SELECT * FROM avdelningar").fetchall()



    sammanstallning = None
    vald_dag = None
    vald_maltid = None
    valda_kosttyper = []
    alt12_valda_kosttyper = []
    anrattning = None
    alt1_anrattning = None
    alt2_anrattning = None
    alt1_valda_kosttyper = []
    alt2_valda_kosttyper = []
    alt1_alt2_resultat = None

    if request.method == "POST":
        vecka = int(request.form.get("vecka", vecka))
        # Specialkost-formulär
        if "visa_specialkost" in request.form or "markera_alla" in request.form:
            vald_dag = request.form.get("dag")
            vald_maltid = request.form.get("maltid")
            valda_kosttyper = request.form.getlist("kosttyp")
            anrattning = request.form.get("anrattning")

            # Del 3: Summering för planering
            if vald_dag and vald_maltid and valda_kosttyper:
                sammanstallning = []
                kopplingar = conn.execute("SELECT * FROM avdelning_kosttyp").fetchall()
                koppling_dict = {}
                for rad in kopplingar:
                    koppling_dict.setdefault(rad["avdelning_id"], {})[rad["kosttyp_id"]] = rad["antal"]
                for avd in avdelningar:
                    avd_resultat = {"namn": avd["namn"], "kostsummering": []}
                    for kostid in valda_kosttyper:
                        kostid_int = int(kostid)
                        antal = koppling_dict.get(avd["id"], {}).get(kostid_int, 0)
                        if antal > 0:
                            namn = next((k["namn"] for k in kosttyper if k["id"] == kostid_int), "")
                            avd_resultat["kostsummering"].append({"namn": namn, "antal": antal})
                    if avd_resultat["kostsummering"]:
                        sammanstallning.append(avd_resultat)

            # Markera alla direkt i registret
            if "markera_alla" in request.form and vald_dag and vald_maltid and valda_kosttyper:
                kopplingar = conn.execute("SELECT * FROM avdelning_kosttyp").fetchall()
                koppling_dict = {}
                for rad in kopplingar:
                    koppling_dict.setdefault(rad["avdelning_id"], {})[rad["kosttyp_id"]] = rad["antal"]
                for avd in avdelningar:
                    for kostid in valda_kosttyper:
                        kostid_int = int(kostid)
                        conn.execute("""
                            INSERT INTO registreringar (vecka, dag, maltid, avdelning_id, kosttyp_id, markerad)
                            VALUES (?, ?, ?, ?, ?, 1)
                            ON CONFLICT(vecka, dag, maltid, avdelning_id, kosttyp_id)
                            DO UPDATE SET markerad=1
                        """, (vecka, vald_dag, vald_maltid, avd["id"], kostid_int))
                conn.commit()

        # Alt1/Alt2-formulär
        elif "visa_alt12" in request.form:
            vald_dag = request.form.get("dag")
            alt1_anrattning = request.form.get("alt1_anrattning")
            alt2_anrattning = request.form.get("alt2_anrattning")
            alt1_valda_kosttyper = request.form.getlist("alt1_kosttyp")
            alt2_valda_kosttyper = request.form.getlist("alt2_kosttyp")

            if vald_dag:
                alt2_rows = conn.execute(
                    "SELECT avdelning_id FROM alt2_markering WHERE vecka = ? AND dag = ?",
                    (vecka, vald_dag)
                ).fetchall()
                alt2_set = {row["avdelning_id"] for row in alt2_rows}

                kopplingar = conn.execute("SELECT * FROM avdelning_kosttyp").fetchall()
                koppling_dict = {}
                for rad in kopplingar:
                    koppling_dict.setdefault(rad["avdelning_id"], {})[rad["kosttyp_id"]] = rad["antal"]

                reg_rows = conn.execute(
                    "SELECT avdelning_id, kosttyp_id, markerad FROM registreringar WHERE vecka = ? AND dag = ? AND maltid = 'Lunch'",
                    (vecka, vald_dag)
                ).fetchall()
                reg_map = {}
                for r in reg_rows:
                    reg_map.setdefault((r["avdelning_id"], r["kosttyp_id"]), r["markerad"])

                boende_rows = conn.execute(
                    "SELECT avdelning_id, antal FROM boende_antal WHERE vecka = ? AND dag = ? AND maltid = 'Lunch'",
                    (vecka, vald_dag)
                ).fetchall()
                boende_map = {row["avdelning_id"]: row["antal"] for row in boende_rows}
                # Om inget boende_antal för aktuell vecka/dag/måltid: sök bakåt efter senaste vecka
                if not boende_map:
                    prev_week = vecka - 1
                    while prev_week >= 1 and not boende_map:
                        prev_rows = conn.execute(
                            "SELECT avdelning_id, antal FROM boende_antal WHERE vecka = ? AND dag = ? AND maltid = 'Lunch'",
                            (prev_week, vald_dag)
                        ).fetchall()
                        if prev_rows:
                            boende_map = {row["avdelning_id"]: row["antal"] for row in prev_rows}
                            break
                        prev_week -= 1

                alt1_avdelningar = []
                alt2_avdelningar = []
                sum_alt1 = 0
                sum_alt2 = 0
                for avd in avdelningar:
                    avd_id = avd["id"]
                    boendeantal = boende_map.get(avd_id)
                    if boendeantal is None:
                        boendeantal = avd["boende_antal"]
                    # Specialkost för Alt1 och Alt2 beräknas separat
                    specialkost_alt1 = 0
                    specialkost_alt2 = 0
                    for kosttyp_id, antal in koppling_dict.get(avd_id, {}).items():
                        if reg_map.get((avd_id, kosttyp_id)):
                            specialkost_alt1 += antal
                            specialkost_alt2 += antal
                        if str(kosttyp_id) in alt1_valda_kosttyper:
                            specialkost_alt1 += antal
                        if str(kosttyp_id) in alt2_valda_kosttyper:
                            specialkost_alt2 += antal
                    if avd_id in alt2_set:
                        normalkost = boendeantal - specialkost_alt2
                        avd_info = {"namn": avd["namn"], "normalkost": normalkost}
                        alt2_avdelningar.append(avd_info)
                        sum_alt2 += normalkost
                    else:
                        normalkost = boendeantal - specialkost_alt1
                        avd_info = {"namn": avd["namn"], "normalkost": normalkost}
                        alt1_avdelningar.append(avd_info)
                        sum_alt1 += normalkost

                alt1_alt2_resultat = {
                    "dag": vald_dag,
                    "alt1": alt1_avdelningar,
                    "alt2": alt2_avdelningar,
                    "sum_alt1": sum_alt1,
                    "sum_alt2": sum_alt2,
                    "alt1_anrattning": alt1_anrattning,
                    "alt2_anrattning": alt2_anrattning,
                    "alt1_valda_kosttyper": alt1_valda_kosttyper,
                    "alt2_valda_kosttyper": alt2_valda_kosttyper
                }

    # Hämta menyförslag från veckomeny-tabellen
    meny_rows = conn.execute("SELECT dag, alt_typ, menytext FROM veckomeny WHERE vecka = ?", (vecka,)).fetchall()
    meny_forslag = {}
    for row in meny_rows:
        dag = row["dag"].lower()
        if dag not in meny_forslag:
            meny_forslag[dag] = {}
        meny_forslag[dag][row["alt_typ"].lower()] = row["menytext"]

    conn.close()
    return render_template("planera.html",
                           vecka=vecka,
                           kosttyper=kosttyper,
                           sammanstallning=sammanstallning,
                           vald_dag=vald_dag,
                           vald_maltid=vald_maltid,
                           valda_kosttyper=valda_kosttyper,
                           alt1_alt2_resultat=alt1_alt2_resultat,
                           anrattning=anrattning,
                           alt1_anrattning=alt1_anrattning,
                           alt2_anrattning=alt2_anrattning,
                           alt1_valda_kosttyper=alt1_valda_kosttyper,
                           alt2_valda_kosttyper=alt2_valda_kosttyper,
                           meny_forslag=meny_forslag)
                        



# ----------- RAPPORT ----------
@app.route("/rapport", methods=["GET", "POST"])

# --- BACKUP AV GAMMAL RAPPORTLOGIK ---
# Se längst upp i denna funktion för backup av tidigare kod!

def rapport():
    # Bestäm vald vecka (POST tar företräde), annars dynamic default
    vecka_post = request.form.get("vecka") if request.method == "POST" else None
    try:
        vecka_init = int(vecka_post) if vecka_post else None
    except ValueError:
        vecka_init = None
    if vecka_init is None:
        vecka_init = get_default_week()
    session["last_week"] = vecka_init

    conn = get_db_connection()
    avdelningar = conn.execute("SELECT id, namn, boende_antal FROM avdelningar").fetchall()
    vecka_boende_map = {}
    for avd in avdelningar:
        rows = conn.execute("SELECT antal FROM boende_antal WHERE avdelning_id = ? AND vecka = ?", (avd["id"], vecka_init)).fetchall()
        per_day_antal = [row["antal"] for row in rows]
        varierat = False
        if len(per_day_antal) > 0:
            unique_antal = set(per_day_antal)
            if len(unique_antal) > 1:
                varierat = True
        vecka_boende_map[avd["id"]] = {"varierat": varierat, "per_day_antal": per_day_antal}

    vecka_vald = str(vecka_init)
    avdelning_vald = None
    vytyp = "dag"
    summerat_resultat = []
    daglista = ["Mån", "Tis", "Ons", "Tors", "Fre", "Lör", "Sön"]

    if request.method == "POST":
        vecka_vald = request.form.get("vecka") or str(vecka_init)
        avdelning_vald = request.form.get("avdelning")
        vytyp = request.form.get("vytyp", "dag")

        if vecka_vald:
            try:
                vecka_int = int(vecka_vald)
            except ValueError:
                vecka_int = vecka_init

            alla_reg = conn.execute("""
                SELECT avdelning_id, dag, maltid, kosttyp_id, markerad
                FROM registreringar
                WHERE vecka = ?
            """, (vecka_int,)).fetchall()
            boende = conn.execute("""
                SELECT avdelning_id, dag, maltid, antal
                FROM boende_antal
                WHERE vecka = ?
            """, (vecka_int,)).fetchall()
            kopplingar = conn.execute("""
                SELECT avdelning_id, kosttyp_id, antal
                FROM avdelning_kosttyp
            """).fetchall()
            formarkerade_kosttyper = conn.execute("""
                SELECT id FROM kosttyper WHERE formarkeras = 1
            """).fetchall()
            alt2_rows = conn.execute("""
                SELECT avdelning_id, dag FROM alt2_markering WHERE vecka = ?
            """, (vecka_int,)).fetchall()
            conn.close()

            boende_map = {(b["avdelning_id"], b["dag"], b["maltid"]): b["antal"] for b in boende}
            kopplingar_map = {(k["avdelning_id"], k["kosttyp_id"]): k["antal"] for k in kopplingar}
            formarkerade_ids = {row["id"] for row in formarkerade_kosttyper}
            alt2_map = {(row["avdelning_id"], row["dag"]) for row in alt2_rows}
            reg_map = {(r["avdelning_id"], r["dag"], r["maltid"], r["kosttyp_id"]): r["markerad"] for r in alla_reg}
            markerad_map = {}
            for key, val in reg_map.items():
                avd_id, dag, maltid, kosttyp_id = key
                if val == 1 and (avd_id, kosttyp_id) in kopplingar_map:
                    markerad_map[key] = True
            for avd in avdelningar:
                for dag in daglista:
                    for maltid in ["Lunch", "Kväll"]:
                        for kosttyp_id in formarkerade_ids:
                            if (avd["id"], kosttyp_id) in kopplingar_map:
                                key = (avd["id"], dag, maltid, kosttyp_id)
                                if key not in reg_map:
                                    markerad_map[key] = True

            for avd in avdelningar:
                if avdelning_vald != "alla" and avdelning_vald and str(avd["id"]) != avdelning_vald:
                    continue
                avd_rader = []
                sum_lunch_normal = 0
                sum_lunch_special = 0
                sum_kvall_normal = 0
                sum_kvall_special = 0
                for dag in daglista:
                    rad = {
                        "avdelning": avd["namn"],
                        "dag": dag,
                        "boende": None,
                        "boende_lunch": None,
                        "boende_kvall": None,
                        "lunch_normal": 0,
                        "lunch_special": 0,
                        "kvall_normal": 0,
                        "kvall_special": 0
                    }
                    for maltid in ["Lunch", "Kväll"]:
                        boendeantal = boende_map.get((avd["id"], dag, maltid))
                        if boendeantal is None:
                            if vecka_boende_map[avd["id"]]["per_day_antal"]:
                                boendeantal = vecka_boende_map[avd["id"]]["per_day_antal"][0]
                            else:
                                boendeantal = avd["boende_antal"] or 0
                        if maltid == "Lunch":
                            rad["boende_lunch"] = boendeantal
                        else:
                            rad["boende_kvall"] = boendeantal
                        if rad["boende"] is None:
                            rad["boende"] = "varierat" if vecka_boende_map[avd["id"]]["varierat"] else boendeantal
                        special = 0
                        for (a_id, d, m, kost_id), is_marked in markerad_map.items():
                            if a_id == avd["id"] and d == dag and m == maltid and is_marked:
                                special += kopplingar_map.get((avd["id"], kost_id), 1)
                        normalkost = boendeantal - special
                        if maltid == "Lunch":
                            rad["lunch_special"] = special
                            rad["lunch_normal"] = normalkost
                            sum_lunch_special += special
                            sum_lunch_normal += normalkost
                        else:
                            rad["kvall_special"] = special
                            rad["kvall_normal"] = normalkost
                            sum_kvall_special += special
                            sum_kvall_normal += normalkost
                    avd_rader.append(rad)
                if vytyp == "dag":
                    for i, rad in enumerate(avd_rader):
                        if i > 0:
                            rad["avdelning"] = ""
                        summerat_resultat.append(rad)
                    summerat_resultat.append({
                        "avdelning": avd["namn"] + " (SUMMA)",
                        "dag": "",
                        "boende": "",
                        "lunch_normal": sum_lunch_normal,
                        "lunch_special": sum_lunch_special,
                        "kvall_normal": sum_kvall_normal,
                        "kvall_special": sum_kvall_special
                    })
                elif vytyp == "vecka":
                    summerat_resultat.append({
                        "avdelning": avd["namn"],
                        "dag": "SUMMA",
                        "boende": "",
                        "lunch_normal": sum_lunch_normal,
                        "lunch_special": sum_lunch_special,
                        "kvall_normal": sum_kvall_normal,
                        "kvall_special": sum_kvall_special
                    })

    return render_template("rapport.html",
                           avdelningar=avdelningar,
                           vecka_vald=vecka_vald,
                           avdelning_vald=avdelning_vald,
                           vytyp=vytyp,
                           summerat_resultat=summerat_resultat)





@app.route("/veckovy_redirect")
def veckovy_redirect():
    # Redirect to dynamic default week instead of week 1
    return redirect(url_for("veckovy", vecka=get_default_week()))

@app.route("/planera_redirect")
def planera_redirect():
    # Dynamisk redirect till planeringsvy för aktuell/senast vald vecka
    return redirect(url_for("planera", vecka=get_default_week()))




@app.route("/registrera_klick", methods=["POST"])
def registrera_klick():
    data = request.get_json()
    if not isinstance(data, list):
        data = [data]
    conn = get_db_connection()
    for klick in data:
        vecka = klick.get("vecka")
        dag = klick.get("dag")
        maltid = klick.get("maltid")
        avdelning_id = klick.get("avdelning_id")
        kosttyp_id = klick.get("kosttyp_id")
        markerad = klick.get("markerad")
        if not all([vecka, dag, maltid, avdelning_id, kosttyp_id]):
            continue
        conn.execute("""
            INSERT INTO registreringar (vecka, dag, maltid, avdelning_id, kosttyp_id, markerad)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(vecka, dag, maltid, avdelning_id, kosttyp_id)
            DO UPDATE SET markerad=excluded.markerad
        """, (vecka, dag, maltid, avdelning_id, kosttyp_id, int(markerad)))
    conn.commit()
    conn.close()
    return {"status": "ok"}






# Menyimport rutter
@app.route("/meny_import")
def meny_import():
    if not session.get("admin"):
        return redirect(url_for("avdelning_login"))
    return render_template("meny_import.html")

@app.route("/upload_meny", methods=["POST"])
def upload_meny():
    if not session.get("admin"):
        return jsonify({"success": False, "error": "Inte inloggad som admin"})
    
    if "menu_file" not in request.files:
        return jsonify({"success": False, "error": "Ingen fil vald"})

    file = request.files["menu_file"]
    if not file.filename or file.filename == "":
        return jsonify({"success": False, "error": "Ingen fil vald"})
    
    if file and allowed_file(file.filename):
        try:
            # Säkert filnamn
            filename = secure_filename(file.filename)  # file.filename har nu kontrollerats
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            
            # Importera och parsa menyn
            from meny_import import MenyImporter
            importer = MenyImporter()
            result = importer.parse_word_document(filepath)

            # Ta bort temporär fil
            os.remove(filepath)

            if result.get("success"):
                # Multiweek: return all weeks and their menus
                return jsonify({
                    "success": True,
                    "weeks_data": result["weeks"],
                })
            else:
                return jsonify({"success": False, "error": result.get("error", "Okänt fel vid parsing")})

        except Exception as e:
            # Ta bort fil om något gick fel
            if "filepath" in locals() and os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"success": False, "error": f"Fel vid import: {str(e)}"})

    return jsonify({"success": False, "error": "Filtyp inte tillåten"})

@app.route("/spara_meny", methods=["POST"])
def spara_meny():
    if not session.get("admin"):
        return jsonify({"success": False, "error": "Inte inloggad som admin"})
    
    try:
        data = request.get_json()
        weeks_data = data.get("weeks_data")
        if not weeks_data or not isinstance(weeks_data, dict):
            return jsonify({"success": False, "error": "Ofullständiga data"})

        from meny_import import save_imported_menus
        conn = sqlite3.connect(DB_PATH)
        all_success = True
        failed_weeks = []
        for vecka_str, meny_data in weeks_data.items():
            try:
                vecka = int(vecka_str)
                success = save_imported_menus(conn, vecka, meny_data)
                if not success:
                    all_success = False
                    failed_weeks.append(vecka)
            except Exception:
                all_success = False
                failed_weeks.append(vecka_str)
        conn.close()

        if all_success:
            return jsonify({"success": True, "message": f"Menyer för veckor {', '.join(str(w) for w in weeks_data.keys())} har sparats!"})
        else:
            return jsonify({"success": False, "error": f"Fel vid sparande för veckor: {', '.join(str(w) for w in failed_weeks)}"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Fel vid sparande: {str(e)}"})


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "initdb":
            print("⚙️ Initierar ny databas...")
            init_db()
            print("✅ Databasen är nu nollställd och klar att användas!")
        elif sys.argv[1] == "testdata":
            print("🧪 Skapar testdata...")
            skapa_testdata()
    else:
        app.run(host="0.0.0.0", debug=True)


