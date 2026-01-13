from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

from core.db import create_all, get_session, init_engine
from core.models import AuditEvent


def _init_db(db_url: str):
    # Force re-init engine pointing at isolated sqlite file
    init_engine(db_url, force=True)
    create_all()


def _seed_old_new(now):
    db = get_session()
    try:
        old_ts = now - timedelta(days=200)
        for i in range(2):
            db.add(
                AuditEvent(
                    ts=old_ts,
                    tenant_id=1,
                    actor_user_id=1,
                    actor_role="admin",
                    event="test",
                    payload={"i": i},
                    request_id="seed-old",
                )
            )
        db.add(
            AuditEvent(
                ts=now - timedelta(days=1),
                tenant_id=1,
                actor_user_id=1,
                actor_role="admin",
                event="test",
                payload={"i": "new"},
                request_id="seed-new",
            )
        )
        db.commit()
    finally:
        db.close()


def test_cli_dry_run_counts(tmp_path):
    db_file = tmp_path / "audit_cli1.db"
    db_url = f"sqlite:///{db_file}"
    _init_db(db_url)
    now = datetime.now(UTC)
    _seed_old_new(now)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    env["DATABASE_URL"] = db_url
    proc = subprocess.run(
        [sys.executable, "scripts/audit_retention_cleanup.py", "--days", "90", "--dry-run"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "would delete 2 audit events" in proc.stdout, proc.stdout


def test_cli_real_purge_then_idempotent(tmp_path):
    db_file = tmp_path / "audit_cli2.db"
    db_url = f"sqlite:///{db_file}"
    _init_db(db_url)
    now = datetime.now(UTC)
    _seed_old_new(now)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    env["DATABASE_URL"] = db_url
    proc1 = subprocess.run(
        [sys.executable, "scripts/audit_retention_cleanup.py", "--days", "90"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc1.returncode == 0, proc1.stderr
    assert "deleted 2 audit events" in proc1.stdout, proc1.stdout
    # second run
    proc2 = subprocess.run(
        [sys.executable, "scripts/audit_retention_cleanup.py", "--days", "90"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc2.returncode == 0, proc2.stderr
    assert "deleted 0 audit events" in proc2.stdout
