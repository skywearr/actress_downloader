from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from actress_downloader.config import AppConfig, DEFAULT_DATABASE_NAME
from actress_downloader.storage import (
    CatalogRepository,
    DatabaseCreationPermissionError,
    ensure_database_exists,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize the PostgreSQL schema for the catalog app.")
    parser.add_argument("--config", help="Path to the TOML config file")
    parser.add_argument(
        "--database-name",
        help=(
            "Optional override only if you had to manually create a different database. "
            f"Default is the fixed name `{DEFAULT_DATABASE_NAME}`."
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = AppConfig.from_file(Path(args.config) if args.config else None)
    postgres = config.postgres.with_database(args.database_name) if args.database_name else config.postgres
    database_url = postgres.database_url

    try:
        created = ensure_database_exists(database_url)
    except DatabaseCreationPermissionError as exc:
        print(f"Cannot create database automatically: {exc.database_name}")
        print("Please create the database manually with a PostgreSQL account that has CREATEDB privilege.")
        print(
            "After creating it, rerun this command. "
            "If you created a different database name, pass `--database-name <name>`."
        )
        return 2

    repository = CatalogRepository(
        database_url=database_url,
        schema_path=config.paths.schema_file,
    )
    repository.initialize()
    action = "created and initialized" if created else "initialized"
    print(f"Database {postgres.database} {action} using {config.paths.schema_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
