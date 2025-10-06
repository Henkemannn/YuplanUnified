#!/usr/bin/env python3
"""Simple semantic version bumper.

Usage:
  python tools/bump_version.py minor
  python tools/bump_version.py patch --current 1.2.3
Writes/updates VERSION file and prints new version to stdout.
"""
import argparse
import pathlib
import re
import sys

VERSION_FILE = pathlib.Path("VERSION")


def read_version(cur_arg: str | None) -> str:
    if cur_arg:
        return cur_arg
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    print("No VERSION file – start with 0.1.0 by passing --current 0.1.0", file=sys.stderr)
    sys.exit(1)


def bump(ver: str, kind: str) -> str:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", ver)
    if not m:
        print(f"Unsupported version format: {ver}", file=sys.stderr)
        sys.exit(2)
    major, minor, patch = map(int, m.groups())
    if kind == "major":
        major, minor, patch = major + 1, 0, 0
    elif kind == "minor":
        minor, patch = minor + 1, 0
    elif kind == "patch":
        patch += 1
    else:
        print("kind must be one of: major, minor, patch", file=sys.stderr)
        sys.exit(3)
    return f"{major}.{minor}.{patch}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["major", "minor", "patch"], help="Which segment to bump")
    ap.add_argument("--current", help="Override current version (otherwise read VERSION)")
    args = ap.parse_args()
    cur = read_version(args.current)
    new = bump(cur, args.kind)
    VERSION_FILE.write_text(new + "\n")
    print(new)


if __name__ == "__main__":
    main()
