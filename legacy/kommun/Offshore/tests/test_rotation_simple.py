import sqlite3

import rotation_simple as rs


def _time_part(ts: str) -> str:
    return ts.split("T", 1)[1]


def test_two_week_block_basic():
    base = rs.generate_two_week_block_for_cook("2025-01-03", "Kokk 1")  # Friday
    # Should produce 15 slots total (2 on day 1, 1 on day 8, plus 12 others)
    assert len(base) == 15

    # Day 1 split into two slots: 09-15 snu_till_natt, 23-07 natt
    s1 = base[0]
    assert _time_part(s1.start_ts) == "09:00"
    assert _time_part(s1.end_ts) == "15:00"
    assert s1.note == "snu_till_natt"

    s2 = base[1]
    assert _time_part(s2.start_ts) == "23:00"
    assert _time_part(s2.end_ts) == "07:00"
    assert s2.note == "natt"

    # Day 8 (index 8) is 15-23 snu_till_dag
    s8 = base[8]
    assert _time_part(s8.start_ts) == "15:00"
    assert _time_part(s8.end_ts) == "23:00"
    assert s8.note == "snu_till_dag"

    # Days 9-14 (indices 9..14) are day shifts 07-19
    for i in range(9, 15):
        assert _time_part(base[i].start_ts) == "07:00"
        assert _time_part(base[i].end_ts) == "19:00"
        assert base[i].note == "dag"


def test_baseline_6_cooks_length():
    slots = rs.generate_baseline_schedule_6_cooks("2025-01-03", weeks=6)
    assert len(slots) == 6 * 15
    roles = {s.role for s in slots}
    assert roles == {f"Kokk {i}" for i in range(1, 7)}


def test_persist_slots_sqlite(tmp_path):
    dbp = tmp_path / "turnus_simple.db"
    slots = rs.generate_baseline_schedule_6_cooks("2025-01-03", weeks=6)
    created = rs.persist_slots_sqlite(db_path=dbp.as_posix(), rig_id=1, slots=slots, status="planned")
    assert created == len(slots)
    con = sqlite3.connect(dbp.as_posix())
    try:
        row = con.execute("SELECT COUNT(*) FROM turnus_slots").fetchone()
        assert row is not None
        assert row[0] == created
    finally:
        con.close()
