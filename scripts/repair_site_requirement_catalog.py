from __future__ import annotations

import argparse
from typing import Sequence

from core.admin_repo import DietTypesRepo, SitesRepo


def _resolve_site_id(site_id: str | None, site_name: str | None) -> str:
    if site_id:
        return site_id.strip()
    if not site_name:
        raise SystemExit("site-id or site-name is required")

    target = site_name.strip().lower()
    for row in SitesRepo().list_sites():
        if str(row.get("name", "")).strip().lower() == target:
            return str(row["id"])
    raise SystemExit(f"site not found: {site_name}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair a site's specialkost catalog to atomic requirement rows.")
    parser.add_argument("--site-id", help="Site id to repair")
    parser.add_argument("--site-name", help="Site name to repair")
    args = parser.parse_args(list(argv) if argv is not None else None)

    resolved_site_id = _resolve_site_id(args.site_id, args.site_name)
    repaired_ids = DietTypesRepo().repair_site_atomic_catalog(resolved_site_id)
    print(f"repaired {len(repaired_ids)} dietary type rows for site {resolved_site_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())