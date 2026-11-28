"""Pinned SQLite Notes trigger definition from migration 0008."""

from __future__ import annotations

import hashlib


NOTES_VERSION_BUMP_TRIGGER_NAME = "notes_version_bump_trg"
NOTES_VERSION_BUMP_TRIGGER_SQL = """CREATE TRIGGER notes_version_bump_trg
                AFTER UPDATE ON notes
                FOR EACH ROW
                BEGIN
                    UPDATE notes
                    SET version = COALESCE(version, 0) + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rowid = NEW.rowid;
                END"""
NOTES_VERSION_BUMP_TRIGGER_SHA256 = (
    "971b0e0cbdc2a06dbb6fca8589a20bbd70749f7ccb5d458692ea53c6f7a37c69"
)


class UnexpectedNotesVersionTrigger(RuntimeError):
    pass


def has_expected_notes_version_trigger(connection) -> bool:
    rows = connection.exec_driver_sql(
        "SELECT name, tbl_name, sql FROM sqlite_master "
        "WHERE type = 'trigger' AND "
        "(tbl_name = 'notes' OR name = ?)",
        (NOTES_VERSION_BUMP_TRIGGER_NAME,),
    ).mappings().all()
    if not rows:
        return False
    if (
        len(rows) == 1
        and rows[0]["name"] == NOTES_VERSION_BUMP_TRIGGER_NAME
        and rows[0]["tbl_name"] == "notes"
        and rows[0]["sql"] is not None
        and hashlib.sha256(rows[0]["sql"].encode("utf-8")).hexdigest()
        == NOTES_VERSION_BUMP_TRIGGER_SHA256
    ):
        return True
    raise UnexpectedNotesVersionTrigger(
        "Unexpected SQLite trigger definition affecting notes"
    )
