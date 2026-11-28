from __future__ import annotations

import argparse

from core.builder_sqlite import initialize_builder_sqlite


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision or upgrade an explicitly selected Builder SQLite database.")
    parser.add_argument("--database", required=True, help="Builder SQLite file to provision or upgrade")
    parser.add_argument(
        "--confirm-schema-upgrade",
        action="store_true",
        required=True,
        help="Confirm that this command may change the selected database schema and legacy rows",
    )
    args = parser.parse_args()
    print(f"Builder schema ready: {initialize_builder_sqlite(args.database)}")


if __name__ == "__main__":
    main()
