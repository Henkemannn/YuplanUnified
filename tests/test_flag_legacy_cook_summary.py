from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout

from core.db import create_all, get_session, init_engine
from core.models import Tenant, TenantFeatureFlag
from scripts.flag_legacy_cook_summary import FLAG_NAME, main as cli_main


def _setup(db_url: str):
    os.environ["DATABASE_URL"] = db_url
    init_engine(db_url, force=True)
    create_all()
    db = get_session()
    try:
        # Tenants
        t1 = Tenant(name="CLIT1")
        t2 = Tenant(name="CLIT2")
        db.add_all([t1, t2])
        db.commit()
        db.refresh(t1)
        db.refresh(t2)
        # Enable flag on t1 only
        db.add(TenantFeatureFlag(tenant_id=t1.id, name=FLAG_NAME, enabled=True))
        db.commit()
        return t1.id, t2.id
    finally:
        db.close()


def test_cli_summary_table(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'cli_flag.db'}"
    _setup(db_url)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(["--format", "table"])
    out = buf.getvalue()
    assert code == 0
    assert "Enabled: 1" in out
    assert "CLIT1" in out and "CLIT2" in out


def test_cli_summary_json(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'cli_flag2.db'}"
    t1, t2 = _setup(db_url)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(["--format", "json"])
    out = buf.getvalue()
    assert code == 0
    payload = json.loads(out)
    assert payload["total_enabled"] == 1
    ids = {r["id"] for r in payload["tenants"]}
    assert t1 in ids and t2 not in ids
