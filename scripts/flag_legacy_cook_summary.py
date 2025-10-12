"""CLI: summarize usage of allow_legacy_cook_create feature flag.

Usage:
  python scripts/flag_legacy_cook_summary.py --format table
  python scripts/flag_legacy_cook_summary.py --format json

Outputs either a simple aligned table or JSON document:
{
  "total_enabled": <int>,
  "tenants": [ {"id": int, "name": str, "active": bool, "enabled": bool} ]
}

Assumptions:
 - Direct DB access via core.db.init_engine/get_session
 - Flag is tenant-scoped in TenantFeatureFlag rows
 - Safe read-only query
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass

# Ensure project root on sys.path BEFORE importing core.*
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.config import Config
from core.db import get_session, init_engine
from core.models import Tenant, TenantFeatureFlag

FLAG_NAME = "allow_legacy_cook_create"


@dataclass
class TenantFlagRow:
    id: int
    name: str
    active: bool
    enabled: bool


def load_rows() -> list[TenantFlagRow]:
    db = get_session()
    try:
        tenants = db.query(Tenant).all()
        # Preload flags for only relevant flag to avoid cartesian expansion
        flag_map: dict[int, bool] = {
            r.tenant_id: True
            for r in db.query(TenantFeatureFlag)
            .filter(TenantFeatureFlag.name == FLAG_NAME, TenantFeatureFlag.enabled.is_(True))
            .all()
        }
        out: list[TenantFlagRow] = []
        for t in tenants:
            out.append(
                TenantFlagRow(
                    id=t.id, name=t.name, active=t.active, enabled=flag_map.get(t.id, False)
                )
            )
        return out
    finally:
        db.close()


def fmt_table(rows: list[TenantFlagRow]) -> str:
    if not rows:
        return "(no tenants)"
    # Determine widths
    id_w = max(len("id"), max(len(str(r.id)) for r in rows))
    name_w = max(len("name"), max(len(r.name) for r in rows))
    active_w = len("active")
    enabled_w = len("legacy_flag")
    header = f"{'id'.ljust(id_w)}  {'name'.ljust(name_w)}  {'active'.ljust(active_w)}  {'legacy_flag'.ljust(enabled_w)}"
    sep = f"{'-' * id_w}  {'-' * name_w}  {'-' * active_w}  {'-' * enabled_w}"
    lines = [header, sep]
    for r in rows:
        lines.append(
            f"{str(r.id).ljust(id_w)}  {r.name.ljust(name_w)}  {str(r.active).ljust(active_w)}  {str(r.enabled).ljust(enabled_w)}"
        )
    enabled_count = sum(1 for r in rows if r.enabled)
    lines.append("")
    lines.append(f"Total tenants: {len(rows)}  Enabled: {enabled_count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize legacy cook flag usage")
    parser.add_argument(
        "--format", choices=["table", "json"], default="table", help="Output format"
    )
    args = parser.parse_args(argv)

    cfg = Config.from_env()
    init_engine(cfg.database_url)
    rows = load_rows()
    if args.format == "json":
        payload = {
            "total_enabled": sum(1 for r in rows if r.enabled),
            "tenants": [r.__dict__ for r in rows if r.enabled],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(fmt_table(rows))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
