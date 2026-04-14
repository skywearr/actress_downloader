from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from datetime import date

import psycopg
from psycopg import errors
from psycopg.sql import SQL, Identifier

from actress_downloader.domain import PerformerIdentity, WorkRecord
from actress_downloader.utils import normalize_text


class CatalogRepository:
    def __init__(self, database_url: str, schema_path: Path) -> None:
        self._database_url = database_url
        self._schema_path = schema_path

    def initialize(self) -> None:
        schema_statements = self._load_schema_statements()
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                for statement in schema_statements:
                    cursor.execute(statement)
            connection.commit()

    def persist_works(self, works: list[WorkRecord]) -> None:
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                for work in works:
                    work_id = self._upsert_work(cursor, work)

                    for index, performer_credit in enumerate(work.performers):
                        performer_id = self._upsert_performer(cursor, performer_credit.to_identity())
                        cursor.execute(
                            """
                            INSERT INTO work_performers (work_id, performer_id, role, sort_order)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (work_id, performer_id) DO UPDATE SET
                                role = EXCLUDED.role,
                                sort_order = EXCLUDED.sort_order
                            """,
                            (work_id, performer_id, performer_credit.role, index),
                        )

                    for tag in work.tags:
                        tag_id = self._upsert_tag(cursor, tag)
                        cursor.execute(
                            """
                            INSERT INTO work_tags (work_id, tag_id, source)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (work_id, tag_id) DO NOTHING
                            """,
                            (work_id, tag_id, "pipeline"),
                        )

                    cursor.execute(
                        """
                        INSERT INTO source_records (entity_type, entity_key, source_name, source_url, raw_payload)
                        VALUES (%s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (entity_type, entity_key, source_name) DO UPDATE SET
                            source_url = EXCLUDED.source_url,
                            raw_payload = EXCLUDED.raw_payload
                        """,
                        (
                            "work",
                            work.code,
                            work.source_name,
                            work.source_url,
                            json.dumps(work.to_dict(), ensure_ascii=False),
                        ),
                    )

            connection.commit()

    @property
    def database_url(self) -> str:
        return self._database_url

    def _upsert_work(self, cursor: psycopg.Cursor, work: WorkRecord) -> int:
        release_date = normalize_release_date(work.release_date)
        cursor.execute(
            """
            INSERT INTO works (code, title, release_date, studio, series, synopsis, source_name, source_url, extra)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title,
                release_date = EXCLUDED.release_date,
                studio = EXCLUDED.studio,
                series = EXCLUDED.series,
                synopsis = EXCLUDED.synopsis,
                source_name = EXCLUDED.source_name,
                source_url = EXCLUDED.source_url,
                extra = EXCLUDED.extra,
                updated_at = NOW()
            RETURNING id
            """,
            (
                work.code,
                work.title,
                release_date,
                work.studio,
                work.series,
                work.synopsis,
                work.source_name,
                work.source_url,
                json.dumps(work.extra, ensure_ascii=False),
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Unable to upsert work {work.code}")
        return int(row[0])

    def _upsert_performer(self, cursor: psycopg.Cursor, performer: PerformerIdentity) -> int:
        normalized_name = normalize_text(performer.canonical_name)
        cursor.execute(
            """
            INSERT INTO performers (canonical_name, normalized_name, confidence, source)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (normalized_name) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source
            RETURNING id
            """,
            (performer.canonical_name, normalized_name, performer.confidence, performer.source),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Unable to upsert performer {performer.canonical_name}")
        performer_id = int(row[0])

        for alias in performer.aliases:
            cursor.execute(
                """
                INSERT INTO performer_aliases (performer_id, alias, normalized_alias, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (performer_id, normalized_alias) DO UPDATE SET
                    alias = EXCLUDED.alias,
                    source = EXCLUDED.source
                """,
                (performer_id, alias, normalize_text(alias), performer.source),
            )

        return performer_id

    def _upsert_tag(self, cursor: psycopg.Cursor, name: str) -> int:
        category = name.split(":", 1)[0] if ":" in name else "general"
        cursor.execute(
            """
            INSERT INTO tags (name, category)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET
                category = EXCLUDED.category
            RETURNING id
            """,
            (name, category),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Unable to upsert tag {name}")
        return int(row[0])

    def _load_schema_statements(self) -> list[str]:
        raw_sql = self._schema_path.read_text(encoding="utf-8")
        return [
            statement.strip()
            for statement in raw_sql.split(";")
            if statement.strip()
        ]


def normalize_release_date(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized == "0000-00-00":
        return None
    try:
        date.fromisoformat(normalized)
    except ValueError:
        return None
    return normalized


class DatabaseCreationPermissionError(RuntimeError):
    def __init__(self, database_name: str) -> None:
        super().__init__(f"Insufficient privilege to create database {database_name!r}.")
        self.database_name = database_name


def ensure_database_exists(database_url: str) -> bool:
    parsed = urlparse(database_url)
    database_name = parsed.path.lstrip("/")
    if not database_name:
        raise ValueError("DATABASE_URL must contain a database name.")

    last_error: Exception | None = None
    for admin_database in ("postgres", "template1"):
        admin_url = urlunparse(parsed._replace(path=f"/{admin_database}"))
        try:
            with psycopg.connect(admin_url, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
                    exists = cursor.fetchone()
                    if exists is not None:
                        return False

                    try:
                        cursor.execute(SQL("CREATE DATABASE {}").format(Identifier(database_name)))
                    except errors.DuplicateDatabase:
                        return False
                    except errors.InsufficientPrivilege as exc:
                        raise DatabaseCreationPermissionError(database_name) from exc
                    return True
        except DatabaseCreationPermissionError:
            raise
        except psycopg.Error as exc:
            last_error = exc

    raise RuntimeError(
        "Unable to connect to an admin database (`postgres` or `template1`) to create the target database."
    ) from last_error
