from __future__ import annotations

import argparse
from pathlib import Path

from actress_downloader.config import AppConfig, DEFAULT_DATABASE_NAME
from actress_downloader.connectors.seed import SeedCatalogConnector
from actress_downloader.llm import build_work_tagger
from actress_downloader.pipeline import run_catalog_pipeline
from actress_downloader.sidecar import SidecarExporter
from actress_downloader.storage import (
    CatalogRepository,
    DatabaseCreationPermissionError,
    ensure_database_exists,
)
from actress_downloader.tagging import TaggingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve performer aliases, collect work codes, tag them, and export metadata."
    )
    parser.add_argument("name", help="Performer name or alias")
    parser.add_argument("--config", help="Path to the TOML config file")
    parser.add_argument("--seed-file", help="Offline catalog seed used by the MVP connector")
    parser.add_argument(
        "--database-name",
        help=(
            "Optional override only for exceptional cases where you manually created a different database. "
            f"Defaults to the fixed name `{DEFAULT_DATABASE_NAME}`."
        ),
    )
    parser.add_argument("--library-root", help="Root directory for exported sidecar metadata")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = AppConfig.from_file(Path(args.config) if args.config else None)
    postgres = config.postgres.with_database(args.database_name) if args.database_name else config.postgres

    connector = SeedCatalogConnector(Path(args.seed_file) if args.seed_file else config.paths.seed_file)
    repository = CatalogRepository(
        database_url=postgres.database_url,
        schema_path=config.paths.schema_file,
    )
    exporter = SidecarExporter(Path(args.library_root) if args.library_root else config.paths.library_root)
    tagger = TaggingService(llm_tagger=build_work_tagger(config.llm))
    try:
        ensure_database_exists(repository.database_url)
    except DatabaseCreationPermissionError as exc:
        print(
            f"Cannot create database automatically: {exc.database_name}. "
            "Please create it manually, then rerun this command."
        )
        if not args.database_name:
            print(
                "If you must use a different database name, rerun with "
                f"`--database-name <name>` instead of changing the config file."
            )
        return 2

    result = run_catalog_pipeline(
        query_name=args.name,
        connector=connector,
        repository=repository,
        exporter=exporter,
        tagger=tagger,
    )

    if result.review_required:
        print("Manual review required.")
        if result.performer_candidates:
            print("Candidates:")
            for performer in result.performer_candidates:
                aliases = ", ".join(performer.aliases) if performer.aliases else "no aliases"
                print(f"- {performer.canonical_name} ({aliases})")
        for error in result.errors:
            print(f"- {error}")
        return 2

    performer = result.performer
    assert performer is not None
    print(f"Resolved performer: {performer.canonical_name}")
    print(f"Aliases: {', '.join(performer.aliases) if performer.aliases else '(none)'}")
    print(f"LLM provider: {config.llm.provider} / model: {config.llm.model}")
    print(f"Works found: {len(result.works)}")
    for work in result.works:
        performer_names = ", ".join(credit.canonical_name for credit in work.performers)
        print(f"- {work.code}: {work.title or '(untitled)'} [{performer_names}]")
        print(f"  tags: {', '.join(work.tags)}")
    print(f"Exported sidecars: {len(result.exported_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
