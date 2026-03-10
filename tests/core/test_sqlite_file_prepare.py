from __future__ import annotations

from pathlib import Path

from core.db import ensure_sqlite_file_ready


def test_ensure_sqlite_file_ready_creates_parent_and_file(tmp_path: Path):
    db_file = tmp_path / "nested" / "yuplan_pilot.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    prepared = ensure_sqlite_file_ready(db_url)

    assert prepared is not None
    assert db_file.parent.exists()
    assert db_file.exists()


def test_ensure_sqlite_file_ready_ignores_memory_sqlite():
    prepared = ensure_sqlite_file_ready("sqlite:///:memory:")
    assert prepared is None
