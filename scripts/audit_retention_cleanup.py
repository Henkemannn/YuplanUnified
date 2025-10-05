from __future__ import annotations

import argparse
import os
import sys
from contextlib import suppress
from datetime import UTC, datetime, timedelta


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Purge old audit events.")
    p.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("AUDIT_RETENTION_DAYS", "90")),
        help="Retention window in days (default env AUDIT_RETENTION_DAYS or 90).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Only count candidates, do not delete.",
    )
    return p.parse_args()


def _ensure_db():  # lazy init DB if not already done (reuse app factory env var if present)
    # If application already initialized elsewhere (tests), skip.
    # For this CLI we attempt a minimal bootstrap using DATABASE_URL or fallback sqlite file.
    from core.db import init_engine
    url = os.getenv("DATABASE_URL") or "sqlite:///app.db"
    init_engine(url)


def count_before(cutoff: datetime) -> int:
    # naive count using query with large size 1 page just for counting? better to do direct count.
    from sqlalchemy import func, select

    from core.db import get_session
    from core.models import AuditEvent
    db = get_session()
    try:
        return db.execute(select(func.count()).select_from(AuditEvent).where(AuditEvent.ts < cutoff)).scalar_one()  # type: ignore[no-any-return]
    finally:
        db.close()


def purge_before(cutoff: datetime) -> int:
    from sqlalchemy import delete

    from core.db import get_session
    from core.models import AuditEvent
    db = get_session()
    try:
        res = db.execute(delete(AuditEvent).where(AuditEvent.ts < cutoff))
        db.commit()
        return res.rowcount or 0
    finally:
        db.close()


def main() -> int:
    args = _parse_args()
    if args.days < 1:
        print("days must be >= 1", file=sys.stderr)
        return 2
    _ensure_db()
    cutoff = datetime.now(UTC) - timedelta(days=args.days)
    try:
        if args.dry_run:
            n = count_before(cutoff)
            print(f"[DRY-RUN] would delete {n} audit events older than {cutoff.isoformat()}")
        else:
            deleted = purge_before(cutoff)
            print(f"deleted {deleted} audit events older than {cutoff.isoformat()}")
        return 0
    except Exception as e:  # pragma: no cover
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    with suppress(SystemExit):
        sys.exit(main())
