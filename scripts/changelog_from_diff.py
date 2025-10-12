#!/usr/bin/env python3
"""Generate a Markdown changelog snippet from openapi-diff.json.

Usage:
  changelog_from_diff.py <openapi-diff.json> <output.md>

Exits 0 on success, 2 on usage error.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

TEMPLATE = """### OpenAPI changes ({date})\nStatus: **{status}**  ·  Breaking: {n_breaking}  ·  Additions: {n_additions}\n\n{breaking_block}{additions_block}"""


def bullets(items: list[str], max_items: int = 100) -> str:
    if not items:
        return "_None_\n"
    lines = [f"- {it}" for it in items[:max_items]]
    if len(items) > max_items:
        lines.append(f"- …and {len(items) - max_items} more")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:  # noqa: D401
    if len(argv) < 3:
        print(
            "Usage: changelog_from_diff.py <openapi-diff.json> <output.md>",
            file=sys.stderr,
        )
        return 2
    src = Path(argv[1])
    dst = Path(argv[2])
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception as e:  # pragma: no cover - defensive
        print(f"[ERROR] Could not read diff JSON: {e}", file=sys.stderr)
        return 2
    breaking = data.get("breaking", []) or []
    additions = data.get("additions", []) or []
    status = str(data.get("status", "ok"))
    breaking_block = "**Breaking**\n\n" + bullets(breaking)
    additions_block = "\n**Additions**\n\n" + bullets(additions)
    md = TEMPLATE.format(
        date=datetime.now(tz=UTC).strftime("%Y-%m-%d"),  # UTC datestamp
        status=status.upper(),
        n_breaking=len(breaking),
        n_additions=len(additions),
        breaking_block=breaking_block,
        additions_block=additions_block,
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(md, encoding="utf-8")
    print(f"Wrote changelog snippet to {dst}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
