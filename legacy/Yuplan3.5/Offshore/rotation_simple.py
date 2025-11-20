"""
Pure, transparent 2-week schedule generator and SQLite persistence for Yuplan Offshore.
Generates slots exactly per business rules; no templates, no inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Iterable, Optional
import sqlite3


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


@dataclass
class Slot:
    start_ts: str   # "YYYY-MM-DDTHH:MM"
    end_ts: str     # "YYYY-MM-DDTHH:MM"
    role: str       # e.g., "Kokk 1"
    note: Optional[str] = None


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def generate_two_week_block_for_cook(start_friday: str, cook_label: str) -> List[Slot]:
    """
    Genererar EXAKT 14 dagar enligt reglerna:
    - Dag 1 (fre): 09–15 (snu_till_natt), 23–07 (natt)
    - Dag 2–7 (lör–tor): 19–07 (natt)
    - Dag 8 (fre): 15–23 (snu_till_dag)
    - Dag 9–14 (lör–tor): 07–19 (dag)
    Retur: list[Slot]
    """
    start = _parse_date(start_friday)
    out: List[Slot] = []
    # Dag 1
    d1 = start
    out.append(Slot(_iso(datetime(d1.year, d1.month, d1.day, 9, 0)), _iso(datetime(d1.year, d1.month, d1.day, 15, 0)), cook_label, "snu_till_natt"))
    # natt fre->lör (23:00 to next day 07:00)
    out.append(Slot(_iso(datetime(d1.year, d1.month, d1.day, 23, 0)), _iso(datetime(d1.year, d1.month, d1.day, 23, 0) + timedelta(hours=8)), cook_label, "natt"))
    # Dag 2–7: lör–tor natt 19–07 (nästa dag)
    for off in range(1, 7):
        d = start + timedelta(days=off)
        start_dt = datetime(d.year, d.month, d.day, 19, 0)
        end_dt = start_dt + timedelta(hours=12)
        out.append(Slot(_iso(start_dt), _iso(end_dt), cook_label, "natt"))
    # Dag 8: fre 15–23 (snu_till_dag)
    d8 = start + timedelta(days=7)
    out.append(Slot(_iso(datetime(d8.year, d8.month, d8.day, 15, 0)), _iso(datetime(d8.year, d8.month, d8.day, 23, 0)), cook_label, "snu_till_dag"))
    # Dag 9–14: lör–tor dag 07–19
    for off in range(8, 14):
        d = start + timedelta(days=off)
        out.append(Slot(_iso(datetime(d.year, d.month, d.day, 7, 0)), _iso(datetime(d.year, d.month, d.day, 19, 0)), cook_label, "dag"))
    return out


def generate_baseline_schedule_6_cooks(start_friday: str, weeks: int = 6) -> List[Slot]:
    """
    Kedjar 6 kockar (Kokk 1..6) – varje vecka startar ett nytt 14-dagars block för nästa kock.
    - start_friday + 7*w = start för kock n (n = w%6 + 1)
    - weeks anger hur många veckostarter att generera.
    Retur: list[Slot]
    """
    base = _parse_date(start_friday)
    all_slots: List[Slot] = []
    for w in range(weeks):
        cook_n = (w % 6) + 1
        cook_label = f"Kokk {cook_n}"
        sf = (base + timedelta(days=7 * w)).strftime("%Y-%m-%d")
        all_slots.extend(generate_two_week_block_for_cook(sf, cook_label))
    return all_slots


def persist_slots_sqlite(db_path: str, rig_id: int, slots: Iterable[Slot], status: str = "planned") -> int:
    """Skriver list[Slot] till turnus_slots i SQLite.
    - template_id sätts till NULL.
    - role = slot.role, notes = slot.note, status enligt parameter.
    Retur: antal rader som skrivits.
    """
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS turnus_slots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              template_id INTEGER,
              rig_id INTEGER NOT NULL,
              start_ts TEXT NOT NULL,
              end_ts TEXT NOT NULL,
              role TEXT,
              status TEXT NOT NULL DEFAULT 'planned',
              notes TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT
            )
            """
        )
        con.executemany(
            """
            INSERT INTO turnus_slots (template_id, rig_id, start_ts, end_ts, role, status, notes, created_at)
            VALUES (NULL, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ((rig_id, s.start_ts, s.end_ts, s.role, status, s.note) for s in slots)
        )
        con.commit()
        return con.total_changes
    finally:
        try:
            con.close()
        except Exception:
            pass
