from __future__ import annotations

import json
from pathlib import Path

from actress_downloader.domain import WorkRecord


class SidecarExporter:
    def __init__(self, library_root: Path) -> None:
        self._library_root = library_root

    def export_works(self, works: list[WorkRecord]) -> list[str]:
        exported_paths: list[str] = []
        self._library_root.mkdir(parents=True, exist_ok=True)
        for work in works:
            work_dir = self._library_root / work.code
            work_dir.mkdir(parents=True, exist_ok=True)
            metadata_path = work_dir / "metadata.json"
            payload = {
                "code": work.code,
                "title": work.title,
                "release_date": work.release_date,
                "studio": work.studio,
                "series": work.series,
                "performers": [
                    {
                        "canonical_name": performer.canonical_name,
                        "aliases": performer.aliases,
                        "role": performer.role,
                    }
                    for performer in work.performers
                ],
                "tags": work.tags,
                "raw_tags": work.raw_tags,
                "source": {
                    "name": work.source_name,
                    "url": work.source_url,
                },
                "synopsis": work.synopsis,
                "extra": work.extra,
            }
            metadata_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            exported_paths.append(str(metadata_path))
        return exported_paths
