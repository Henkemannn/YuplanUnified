# TEST: Kommentar tillagd av Copilot (2025-09-10)
# rotation.py
# Ny, fristående modul för turnus-logik.
# Använder SQLite (app.db) och tabeller som skapades i Steg 4:
#   turnus_templates, turnus_slots, turnus_account_binding
#
# OBS: Denna modul rör INTE menydelen.

import sqlite3
import json
import csv
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Iterable
from pathlib import Path
from collections import Counter, defaultdict

DB_PATH = Path("app.db")

# ---------- Hjälpfunktioner ----------
def _conn():
    if not DB_PATH.exists():
        raise RuntimeError("Hittar inte app.db i projektroten.")
    conn = sqlite3.connect(DB_PATH.as_posix())
    conn.row_factory = sqlite3.Row
    # Säkerställ FK-stöd i SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    # Se till att ev. extra tabeller för turnus finns
    _ensure_aux_tables(conn)
    return conn

def _ensure_aux_tables(conn: sqlite3.Connection) -> None:
    """Skapar extra hjälptabeller om de saknas."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS turnus_virtual_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rig_id INTEGER NOT NULL,
            label TEXT NOT NULL,          -- t.ex. 'Kokk 1'
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT,
            UNIQUE(rig_id, label)
        )
        """
    )
    # rigs-tabell antas redan finnas via schema/migrationer

def _ensure_rig_exists(conn: sqlite3.Connection, rig_id: int) -> None:
    cur = conn.execute("SELECT 1 FROM rigs WHERE id = ?", (rig_id,))
    if not cur.fetchone():
        # Skapa enkel riggrad om saknas
        conn.execute("INSERT INTO rigs(id, name) VALUES(?, ?)", (rig_id, f"Rigg {rig_id}"))

def _iso(dt: datetime) -> str:
    # ISO8601 utan timezone (vi antar lokal/UTC-hantering i appen)
    return dt.strftime("%Y-%m-%dT%H:%M")

def _parse_date(d: str) -> date:
    # Tillåt 'YYYY-MM-DD'
    return datetime.strptime(d, "%Y-%m-%d").date()

def _parse_ts(ts: str) -> datetime:
    # Tillåt 'YYYY-MM-DDTHH:MM'
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M")

def _parse_time(t: str) -> timedelta:
    # 'HH:MM' -> timedelta
    hh, mm = t.split(":")
    return timedelta(hours=int(hh), minutes=int(mm))

def _daterange(d0: date, d1: date) -> Iterable[date]:
    # Inklusive d1
    cur = d0
    while cur <= d1:
        yield cur
        cur = cur + timedelta(days=1)

# ---------- Templates ----------
def create_template(name: str, pattern: Dict[str, Any], rig_id: Optional[int] = None, is_active: bool = True) -> int:
    """
    Skapa en template.
    pattern: JSON-struktur, ex:
    {
      "weekly": [
        {"weekday": 0, "start": "07:00", "end": "19:00", "role": "dag"},
        {"weekday": 1, "start": "19:00", "end": "07:00", "role": "natt"},
        ...
      ]
    }
    weekday: 0=måndag ... 6=söndag
    """
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO turnus_templates (name, rig_id, pattern_json, is_active, created_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (name, rig_id, json.dumps(pattern), 1 if is_active else 0)
        )
    return cur.lastrowid if cur.lastrowid is not None else -1

def update_template(template_id: int, *, name: Optional[str] = None,
                    pattern: Optional[Dict[str, Any]] = None,
                    rig_id: Optional[int] = None,
                    is_active: Optional[bool] = None) -> None:
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if rig_id is not None:
        fields.append("rig_id = ?")
        values.append(rig_id)
    if pattern is not None:
        fields.append("pattern_json = ?")
        values.append(json.dumps(pattern))
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(1 if is_active else 0)
    if not fields:
        return
    fields.append("updated_at = datetime('now')")
    with _conn() as conn:
        conn.execute(f"UPDATE turnus_templates SET {', '.join(fields)} WHERE id = ?", (*values, template_id))

def set_template_active(template_id: int, active: bool) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE turnus_templates SET is_active = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if active else 0, template_id)
        )

def get_template(template_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        cur = conn.execute("SELECT * FROM turnus_templates WHERE id = ?", (template_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["pattern"] = json.loads(d.pop("pattern_json") or "{}")
        return d

def list_templates(rig_id: Optional[int] = None, active_only: bool = False) -> List[Dict[str, Any]]:
    q = "SELECT * FROM turnus_templates"
    where = []
    params: List[Any] = []
    if rig_id is not None:
        where.append("rig_id = ?")
        params.append(rig_id)
    if active_only:
        where.append("is_active = 1")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY id DESC"
    with _conn() as conn:
        rows = conn.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["pattern"] = json.loads(d.pop("pattern_json") or "{}")
            out.append(d)
        return out

def generate_slots_from_motor_template(template_id: int, start_date: str, end_date: str, rig_id_override: Optional[int] = None) -> int:
    """
    Motor V1: pattern_json structure:
    {
      "type": "motor_v1",
      "meta": {
        "cooks": 6,
        "day_time": {"start": "07:00", "end": "19:00"},
        "night_time": {"start": "19:00", "end": "07:00"},
        "weekdays_day": [0,1,2,3,4,5,6],
        "weekdays_night": [0,1,2,3,4,5,6],
        "start_day_cook": 1,
        "start_night_cook": 2
      }
    }
    Skapar slots med role = "Kokk N" och avancerar N modulo cooks för dag resp. natt var för sig.
    """
    tmpl = get_template(template_id)
    if not tmpl:
        raise ValueError("Template saknas")
    pattern = tmpl.get("pattern") or {}
    if pattern.get("type") != "motor_v1":
        raise ValueError("Template-typ stöds ej för motor")
    meta = pattern.get("meta") or {}
    cooks = int(meta.get("cooks", 6))
    if cooks < 1:
        raise ValueError("cooks måste vara >= 1")
    dt_conf = meta.get("day_time", {"start":"07:00","end":"19:00"})
    nt_conf = meta.get("night_time", {"start":"19:00","end":"07:00"})
    w_day = set(int(x) for x in (meta.get("weekdays_day") or []))
    w_night = set(int(x) for x in (meta.get("weekdays_night") or []))
    day_idx = int(meta.get("start_day_cook", 1))
    night_idx = int(meta.get("start_night_cook", 1))
    # Valfri støtte for snu-dager: liste av 'YYYY-MM-DD' som forskyver indeks en ekstra gang
    snu_dates = set(meta.get("snu_dates") or [])
    rig_id = rig_id_override if rig_id_override is not None else tmpl.get("rig_id")
    if rig_id is None:
        raise ValueError("rig_id krävs (i template eller override)")

    d0 = _parse_date(start_date)
    d1 = _parse_date(end_date)
    to_insert: List[tuple] = []
    for d in _daterange(d0, d1):
        wd = d.weekday()
        ds = d.strftime('%Y-%m-%d')
        if ds in snu_dates:
            # Snudag: roter indekser en ekstra posisjon før generering denne dagen
            day_idx = ((day_idx) % cooks) + 1
            night_idx = ((night_idx) % cooks) + 1
        # Day slot
        if wd in w_day:
            start_dt = _parse_time_to_dt(d, dt_conf.get("start", "07:00"))
            end_dt = _parse_time_to_dt(d, dt_conf.get("end", "19:00"))
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            role = f"Kokk {((day_idx - 1) % cooks) + 1}"
            to_insert.append((template_id, rig_id, _iso(start_dt), _iso(end_dt), role, "planned", None))
            day_idx = ((day_idx) % cooks) + 1
        # Night slot
        if wd in w_night:
            start_dt = _parse_time_to_dt(d, nt_conf.get("start", "19:00"))
            end_dt = _parse_time_to_dt(d, nt_conf.get("end", "07:00"))
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            role = f"Kokk {((night_idx - 1) % cooks) + 1}"
            to_insert.append((template_id, rig_id, _iso(start_dt), _iso(end_dt), role, "planned", None))
            night_idx = ((night_idx) % cooks) + 1

    if not to_insert:
        return 0
    with _conn() as conn:
        _ensure_rig_exists(conn, rig_id)
        conn.executemany(
            """
            INSERT INTO turnus_slots
            (template_id, rig_id, start_ts, end_ts, role, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            to_insert
        )
        return conn.total_changes

# ---------- Slots ----------
def generate_slots_from_template(template_id: int, start_date: str, end_date: str, rig_id_override: Optional[int] = None) -> int:
    """
    Generera slots från en template över ett datumintervall (inklusive end_date).
    Returnerar antal skapade slots.
    """
    tmpl = get_template(template_id)
    if not tmpl:
        raise ValueError("Template saknas")
    pattern = tmpl.get("pattern") or {}
    weekly = pattern.get("weekly") or []
    if not weekly:
        return 0

    rig_id = rig_id_override if rig_id_override is not None else tmpl.get("rig_id")
    if rig_id is None:
        raise ValueError("rig_id krävs (i template eller override)")

    d0 = _parse_date(start_date)
    d1 = _parse_date(end_date)

    to_insert: List[tuple] = []
    for d in _daterange(d0, d1):
        wd = (d.weekday())  # måndag=0..söndag=6 (matchar vårt antagande)
        # matcha alla regler för veckodagen
        for rule in weekly:
            if int(rule.get("weekday", -1)) != wd:
                continue
            start_td = _parse_time(rule["start"])
            end_td = _parse_time(rule["end"])

            start_dt = datetime(d.year, d.month, d.day) + start_td
            end_dt = datetime(d.year, d.month, d.day) + end_td
            # Om sluttiden är före start (t.ex. natt), rulla till nästa dag
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)

            role = rule.get("role")
            to_insert.append((
                template_id,
                rig_id,
                _iso(start_dt),
                _iso(end_dt),
                role or None,
                "planned",
                None  # notes
            ))

    if not to_insert:
        return 0

    with _conn() as conn:
        _ensure_rig_exists(conn, rig_id)
        conn.executemany(
            """INSERT INTO turnus_slots
               (template_id, rig_id, start_ts, end_ts, role, status, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            to_insert
        )
        return conn.total_changes

def list_slots(*,
               template_id: Optional[int] = None,
               rig_id: Optional[int] = None,
               status: Optional[str] = None,
               from_ts: Optional[str] = None,
               to_ts: Optional[str] = None) -> List[Dict[str, Any]]:
    q = "SELECT * FROM turnus_slots"
    where = []
    params: List[Any] = []
    if template_id is not None:
        where.append("template_id = ?")
        params.append(template_id)
    if rig_id is not None:
        where.append("rig_id = ?")
        params.append(rig_id)
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if from_ts is not None:
        where.append("start_ts >= ?")
        params.append(from_ts)
    if to_ts is not None:
        where.append("end_ts <= ?")
        params.append(to_ts)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY start_ts ASC"
    with _conn() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

def clone_slots_interval(
    *,
    rig_id: int,
    src_start_ts: str,
    src_end_ts: str,
    cycles: int = 1,
    period_days: int = 42,
    publish: bool = False,
    skip_duplicates: bool = True,
) -> int:
    """
    Klona alla slots i [src_start_ts, src_end_ts] framåt i tiden i steg om period_days,
    'cycles' antal gånger. Undviker dubbletter om skip_duplicates=True genom att hoppa över
    rader med samma (rig, role, start_ts, end_ts).
    Returnerar totalt antal skapade slots över alla cykler.
    """
    base_slots = list_slots(rig_id=rig_id, from_ts=src_start_ts, to_ts=src_end_ts)
    if not base_slots:
        return 0
    status = "published" if publish else "planned"
    total_created = 0
    with _conn() as conn:
        _ensure_rig_exists(conn, rig_id)
        for c in range(1, cycles + 1):
            offset = timedelta(days=period_days * c)
            to_insert = []
            for s in base_slots:
                st = _parse_ts(s["start_ts"]) + offset
                et = _parse_ts(s["end_ts"]) + offset
                role = s.get("role")
                notes = s.get("notes")
                if skip_duplicates:
                    dup = conn.execute(
                        """
                        SELECT id FROM turnus_slots
                        WHERE rig_id = ? AND role IS ? AND start_ts = ? AND end_ts = ?
                        """,
                        (rig_id, role, _iso(st), _iso(et))
                    ).fetchone()
                    if dup:
                        continue
                to_insert.append((
                    s.get("template_id"),
                    rig_id,
                    _iso(st),
                    _iso(et),
                    role,
                    status,
                    notes
                ))
            if to_insert:
                conn.executemany(
                    """
                    INSERT INTO turnus_slots
                    (template_id, rig_id, start_ts, end_ts, role, status, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    to_insert
                )
                total_created += conn.total_changes
    return total_created

def publish_slots(slot_ids: List[int]) -> int:
    if not slot_ids:
        return 0
    placeholders = ",".join("?" for _ in slot_ids)
    with _conn() as conn:
        conn.execute(
            f"UPDATE turnus_slots SET status='published', updated_at=datetime('now') WHERE id IN ({placeholders})",
            slot_ids
        )
        return conn.total_changes

def delete_slots(slot_ids: List[int]) -> int:
    if not slot_ids:
        return 0
    placeholders = ",".join("?" for _ in slot_ids)
    with _conn() as conn:
        conn.execute(
            f"DELETE FROM turnus_slots WHERE id IN ({placeholders})",
            slot_ids
        )
        return conn.total_changes

# ---------- Binding (user ↔ slot) ----------
def bind_user_to_slot(slot_id: int, user_id: int, notes: Optional[str] = None) -> None:
    """
    Unik binding per slot (enligt schema UNIQUE(slot_id)).
    Om det redan finns en binding för slot: ta bort den först och skapa ny.
    """
    with _conn() as conn:
        conn.execute("DELETE FROM turnus_account_binding WHERE slot_id = ?", (slot_id,))
        conn.execute(
            """INSERT INTO turnus_account_binding (slot_id, user_id, notes, bound_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (slot_id, user_id, notes)
        )

def unbind_user_from_slot(slot_id: int) -> int:
    with _conn() as conn:
        conn.execute("DELETE FROM turnus_account_binding WHERE slot_id = ?", (slot_id,))
        return conn.total_changes

# ---------- Query för preview & view ----------
def preview(rig_id: int, start_ts: str, end_ts: str) -> List[Dict[str, Any]]:
        """
        Hämtar slots (alla status) i intervallet för en rigg.
        Används för /turnus/preview i Steg 6.
        """
        q = """
SELECT s.*, b.user_id, u.name AS user_name
FROM turnus_slots s
LEFT JOIN turnus_account_binding b ON b.slot_id = s.id
LEFT JOIN users u ON u.id = b.user_id
WHERE s.rig_id = ?
    AND s.start_ts < ?
    AND s.end_ts > ?
ORDER BY s.start_ts ASC
        """
        with _conn() as conn:
                rows = conn.execute(q, (rig_id, end_ts, start_ts)).fetchall()
                return [dict(r) for r in rows]

def view(rig_id: int, start_ts: str, end_ts: str) -> List[Dict[str, Any]]:
    """
    Hämtar endast publicerade slots i intervallet för en rigg.
    Används för /turnus/view i Steg 6.
    """
    q = """
    SELECT s.*, b.user_id, u.name AS user_name
    FROM turnus_slots s
    LEFT JOIN turnus_account_binding b ON b.slot_id = s.id
    LEFT JOIN users u ON u.id = b.user_id
    WHERE s.rig_id = ?
      AND s.status = 'published'
      AND s.start_ts >= ?
      AND s.end_ts <= ?
    ORDER BY s.start_ts ASC
    """
    with _conn() as conn:
        rows = conn.execute(q, (rig_id, start_ts, end_ts)).fetchall()
        return [dict(r) for r in rows]
def generate_turnus_for_cooks(
    rig_id: int,
    start_date: str,
    end_date: str,
    cook_names: list,
    snu_days: Optional[List[str]] = None,
    gap_days: Optional[List[str]] = None
) -> int:
    """
    Genererar och skriver hela turnusen för 6 kockar till databasen.
    cook_names: lista med 6 namn (virtuella kockar, kan mappas till riktiga användare)
    snu_days: lista med datumsträngar (YYYY-MM-DD) för snu-dagar
    gap_days: lista med datumsträngar (YYYY-MM-DD) för glapp (ingen kock)
    Returnerar antal skapade slots.
    """
    if len(cook_names) != 6:
        raise ValueError("Exakt 6 kockar krävs")
    snu_set = set(snu_days or [])
    gap_set = set(gap_days or [])
    d0 = _parse_date(start_date)
    d1 = _parse_date(end_date)
    days = list(_daterange(d0, d1))
    slots = []
    cook_idx = 0
    for d in days:
        ds = d.strftime('%Y-%m-%d')
        if ds in gap_set:
            continue  # Ingen kock denna dag
        if ds in snu_set:
            # Snu-dag: rotera kockarna (t.ex. hoppa till nästa)
            cook_idx = (cook_idx + 1) % 6
        cook = cook_names[cook_idx]
        start_dt = datetime(d.year, d.month, d.day, 7, 0)
        end_dt = datetime(d.year, d.month, d.day, 19, 0)
        slots.append((
            None,  # template_id
            rig_id,
            _iso(start_dt),
            _iso(end_dt),
            cook,
            "planned",
            None
        ))
        cook_idx = (cook_idx + 1) % 6
    if not slots:
        return 0
    with _conn() as conn:
        conn.executemany(
            """INSERT INTO turnus_slots
               (template_id, rig_id, start_ts, end_ts, role, status, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            slots
        )
        return conn.total_changes

# ---------- Virtuell kock-mapping ----------
def _normalize_virtual_label(cook_label: str) -> Optional[str]:
    """
    Försök tolka 'Kock 1' / 'Kokk 1' / 'kokk 1' → 'Kokk 1'.
    Returnerar None om ingen siffra hittas.
    """
    if not cook_label:
        return None
    s = cook_label.strip()
    # Plocka ut siffra
    import re
    m = re.search(r"(kokk|kock)\s*(\d+)", s, re.IGNORECASE)
    if not m:
        return None
    n = int(m.group(2))
    if n < 1 or n > 6:
        return None
    return f"Kokk {n}"

def set_virtual_mapping(rig_id: int, mapping: Dict[str, int]) -> None:
    """
    Sätt global mapping för virtuell kocklabel → user_id per rigg.
    mapping: { 'Kokk 1': user_id, ..., 'Kokk 6': user_id }
    """
    with _conn() as conn:
        for label, uid in mapping.items():
            norm = _normalize_virtual_label(label)
            if not norm or not isinstance(uid, int):
                continue
            conn.execute(
                """
                INSERT INTO turnus_virtual_map(rig_id, label, user_id)
                VALUES(?,?,?)
                ON CONFLICT(rig_id, label) DO UPDATE SET user_id=excluded.user_id, updated_at=datetime('now')
                """,
                (rig_id, norm, uid)
            )

def get_virtual_mapping(rig_id: int) -> Dict[str, int]:
    with _conn() as conn:
        rows = conn.execute("SELECT label, user_id FROM turnus_virtual_map WHERE rig_id = ?", (rig_id,)).fetchall()
        return {r["label"]: r["user_id"] for r in rows}

def apply_virtual_mapping(rig_id: int, start_ts: Optional[str] = None, end_ts: Optional[str] = None) -> int:
    """
    Skapa bindings för slots utan binding baserat på global mapping (label → user).
    Returnerar antal skapade bindings.
    """
    mapping = get_virtual_mapping(rig_id)
    if not mapping:
        return 0
    where = ["rig_id = ?"]
    params: List[Any] = [rig_id]
    if start_ts:
        where.append("start_ts >= ?")
        params.append(start_ts)
    if end_ts:
        where.append("end_ts <= ?")
        params.append(end_ts)
    where_clause = " AND ".join(where)
    with _conn() as conn:
        # Hämta slots utan binding
        q = f"""
        SELECT s.* FROM turnus_slots s
        LEFT JOIN turnus_account_binding b ON b.slot_id = s.id
        WHERE {where_clause} AND b.id IS NULL
        """
        slots = conn.execute(q, params).fetchall()
        created = 0
        for s in slots:
            label = _normalize_virtual_label(s["role"] or "")
            if not label:
                continue
            uid = mapping.get(label)
            if not uid:
                continue
            # Bind (ersätter ev. existerande binding, men vi filtrerar redan Null)
            conn.execute("DELETE FROM turnus_account_binding WHERE slot_id = ?", (s["id"],))
            conn.execute(
                "INSERT INTO turnus_account_binding (slot_id, user_id, notes, bound_at) VALUES (?,?,?,datetime('now'))",
                (s["id"], uid, f"auto via {label}")
            )
            created += 1
        return created

# ---------- CSV-import för turnus ----------
def _parse_time_to_dt(d: date, t: str) -> datetime:
    """Tolka tider som '07:00', '23:00', '24:00'. 24:00 → 00:00 nästa dag."""
    hh, mm = [int(x) for x in t.split(":")]
    if hh == 24 and mm == 0:
        # 24:00 → midnatt nästa dag
        return datetime(d.year, d.month, d.day) + timedelta(days=1)
    return datetime(d.year, d.month, d.day, hh, mm)

def import_turnus_csv(csv_path: str, rig_id: int, publish: bool = False) -> int:
    """
    Importera slots direkt från CSV.
    Förväntade kolumner: date,weekday,week_in_cycle,cook,shift,start_time,end_time,special,notes
    - Rader med shift i ('dag','natt') skapar slots
    - "ledig" ignoreras
    - cook mappas till role = 'Kokk N' (normaliserat)
    - notes inkluderar shift/special/notes
    Returnerar antal skapade slots.
    """
    status = "published" if publish else "planned"
    to_insert: List[tuple] = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            shift = (row.get("shift") or "").strip().lower()
            if shift not in ("dag", "natt"):
                continue
            cook_label = row.get("cook") or ""
            label = _normalize_virtual_label(cook_label)
            if not label:
                # Om cook inte matchar 1..6, hoppa
                continue
            ds = row.get("date")
            if not ds:
                continue
            try:
                d = datetime.strptime(ds, "%Y-%m-%d").date()
            except Exception:
                continue
            st = (row.get("start_time") or "").strip() or ("07:00" if shift == "dag" else "19:00")
            et = (row.get("end_time") or "").strip() or ("19:00" if shift == "dag" else "07:00")
            start_dt = _parse_time_to_dt(d, st)
            end_dt = _parse_time_to_dt(d, et)
            # Om sluttid är före start, rulla till nästa dag
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            special = (row.get("special") or "").strip()
            notes_txt = (row.get("notes") or "").strip()
            note = "; ".join(x for x in [f"shift={shift}", f"special={special}" if special else None, notes_txt if notes_txt else None] if x)
            to_insert.append((
                None,
                rig_id,
                _iso(start_dt),
                _iso(end_dt),
                label,   # role = Kokk N
                status,
                note or None
            ))
    if not to_insert:
        return 0
    with _conn() as conn:
        _ensure_rig_exists(conn, rig_id)
        conn.executemany(
            """
            INSERT INTO turnus_slots
            (template_id, rig_id, start_ts, end_ts, role, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            to_insert
        )
        return conn.total_changes


def infer_motor_template_from_csv(csv_path: str, cooks: int = 6) -> Dict[str, Any]:
    """
    Läs ett exempel-CSV (dag/natt) och försök härleda en motor_v1 pattern:
    - weekdays_day / weekdays_night från vilka veckodagar som förekommer
    - day_time / night_time från vanligaste start/slut
    - start_day_cook / start_night_cook från första observerade
    - snu_dates: datum där index inte följer enkel +1-rotation dag för dag
    Returnerar pattern-dict: {"type":"motor_v1","meta":{...}}
    """
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            shift = (r.get("shift") or "").strip().lower()
            if shift not in ("dag", "natt"):
                continue
            ds = (r.get("date") or "").strip()
            cook_label = r.get("cook") or ""
            label = _normalize_virtual_label(cook_label)
            if not label:
                continue
            try:
                d = datetime.strptime(ds, "%Y-%m-%d").date()
            except Exception:
                continue
            st = (r.get("start_time") or "").strip()
            et = (r.get("end_time") or "").strip()
            rows.append({
                "date": d,
                "date_s": ds,
                "shift": shift,
                "label": label,
                "n": int(label.split()[1]),
                "start": st or ("07:00" if shift == "dag" else "19:00"),
                "end": et or ("19:00" if shift == "dag" else "07:00"),
            })

    if not rows:
        raise ValueError("CSV inneholder ingen dag/natt-rader med Kokk 1..6")

    rows.sort(key=lambda r: (r["date"], 0 if r["shift"] == "dag" else 1))
    day_times = Counter()
    night_times = Counter()
    wd_day = set()
    wd_night = set()
    day_seq = []  # (date, n)
    night_seq = []
    for r in rows:
        wd = r["date"].weekday()
        if r["shift"] == "dag":
            wd_day.add(wd)
            day_times[(r["start"], r["end"])] += 1
            day_seq.append((r["date"], r["n"]))
        else:
            wd_night.add(wd)
            night_times[(r["start"], r["end"])] += 1
            night_seq.append((r["date"], r["n"]))

    def most_common_time(counter: Counter, default_start: str, default_end: str):
        if not counter:
            return {"start": default_start, "end": default_end}
        (st, et), _ = counter.most_common(1)[0]
        return {"start": st or default_start, "end": et or default_end}

    meta: Dict[str, Any] = {
        "cooks": cooks,
        "day_time": most_common_time(day_times, "07:00", "19:00"),
        "night_time": most_common_time(night_times, "19:00", "07:00"),
        "weekdays_day": sorted(wd_day),
        "weekdays_night": sorted(wd_night),
        "start_day_cook": (day_seq[0][1] if day_seq else 1),
        "start_night_cook": (night_seq[0][1] if night_seq else 1),
    }

    # Heuristisk snu-dagsdetektion: markera datum där observerat index inte matchar förväntat (+1 modulo cooks)
    snu = set()
    def detect_snu(seq: list[tuple[date, int]], start_idx: int):
        if not seq:
            return
        expected = start_idx
        last_date = seq[0][0]
        for i, (d, n) in enumerate(seq):
            if i == 0:
                continue
            # hoppa över luckor i kalendern påverkar inte +1 per observerad dag
            expected = ((expected) % cooks) + 1
            if n != expected:
                snu.add(d.strftime("%Y-%m-%d"))
                expected = n
    detect_snu(day_seq, meta["start_day_cook"])
    detect_snu(night_seq, meta["start_night_cook"])
    if snu:
        meta["snu_dates"] = sorted(snu)

    return {"type": "motor_v1", "meta": meta}


def generate_turnus_6cook_simple(
    rig_id: int,
    start_date: str,
    weeks: int = 6,
    *,
    night_start: str = "19:00",
    night_end: str = "07:00",
    day_start: str = "07:00",
    day_end: str = "19:00",
    add_snu_notes: bool = True,
    add_prep_note: bool = True,
    skip_duplicates: bool = True,
) -> int:
    """
    Enkel generator för 6-kockars 2/4-mönster:
    - Varje cook har ett 2-veckors block som startar en vecka efter föregående:
      Vecka 1: natt varje dag
      Vecka 2: dag varje dag
    - Fredag i vecka 1 och fredag i vecka 2 markeras som snu-dagar (om add_snu_notes)
    - Fredag i vecka 2 får även 'prep lunch' notis (om add_prep_note)
    - Genererar 'weeks' sammanhängande veckor från start_date (default 6 veckor)
    Obs: För full täckning från dag 1 krävs att start_date ligger på en rotationsgräns
    (t.ex. att föregående cook redan är inne i vecka 2). Denna funktion håller det enkelt.
    """
    d0 = _parse_date(start_date)
    # Generera per vecka i taget; varje ny vecka startar ny kock i vecka 1 (natt), medan förra veckans kock nu är i vecka 2 (dag)
    created = 0
    with _conn() as conn:
        _ensure_rig_exists(conn, rig_id)
        for w in range(weeks):
            block_start = d0 + timedelta(days=7 * w)
            # Bestäm kocknummer (1..6) för denna veckas block
            cook_n = (w % 6) + 1
            role = f"Kokk {cook_n}"
            # Vecka 1 (natt) dagar:
            week1_days = [block_start + timedelta(days=i) for i in range(7)]
            # Vecka 2 (dag) dagar:
            week2_days = [block_start + timedelta(days=7 + i) for i in range(7)]

            # Hjälp: hitta fredag (weekday==4) i respektive vecka
            def week_friday(days: List[date]) -> Optional[date]:
                for d in days:
                    if d.weekday() == 4:
                        return d
                return None

            fri1 = week_friday(week1_days)
            fri2 = week_friday(week2_days)

            # Insert helper med dubblettskontroll
            def insert_slot(day: date, st: str, et: str, note_extra: Optional[str] = None):
                start_dt = _parse_time_to_dt(day, st)
                end_dt = _parse_time_to_dt(day, et)
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                start_s = _iso(start_dt)
                end_s = _iso(end_dt)
                if skip_duplicates:
                    dup = conn.execute(
                        """
                        SELECT id FROM turnus_slots
                        WHERE rig_id = ? AND role = ? AND start_ts = ? AND end_ts = ?
                        """,
                        (rig_id, role, start_s, end_s),
                    ).fetchone()
                    if dup:
                        return 0
                note = None
                if add_snu_notes and ((fri1 and day == fri1) or (fri2 and day == fri2)):
                    note = (note or "") + ("snu" if not note else "; snu")
                if add_prep_note and fri2 and day == fri2:
                    note = (note or "") + ("; prep lunch for incoming" if note else "prep lunch for incoming")
                conn.execute(
                    """
                    INSERT INTO turnus_slots
                    (template_id, rig_id, start_ts, end_ts, role, status, notes, created_at)
                    VALUES (NULL, ?, ?, ?, ?, 'planned', ?, datetime('now'))
                    """,
                    (rig_id, start_s, end_s, role, note),
                )
                return 1

            # Generera vecka 1 (natt)
            for d in week1_days:
                created += insert_slot(d, night_start, night_end)
            # Generera vecka 2 (dag)
            for d in week2_days:
                created += insert_slot(d, day_start, day_end)

    return created