from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from actress_downloader.domain import PerformerCredit, WorkRecord
from actress_downloader.sidecar import SidecarExporter
from actress_downloader.tagging import TaggingService


class SidecarExporterTests(unittest.TestCase):
    def test_export_multi_performer_metadata(self) -> None:
        temp_dir = PROJECT_ROOT / ".tmp_test_sidecar"
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        exporter = SidecarExporter(temp_dir)
        work = WorkRecord(
            code="TEST-001",
            title="多人作品",
            release_date="2024-05-01",
            studio="S1",
            performers=[
                PerformerCredit(canonical_name="三上悠亚", aliases=["鬼头桃菜"]),
                PerformerCredit(canonical_name="桥本有菜", aliases=["Hashimoto Arina"]),
            ],
            raw_tags=["HD"],
            source_name="test",
            source_url="https://example.test/works/test-001",
        )

        tagged_work = TaggingService().tag_work(work)
        exported_files = exporter.export_works([tagged_work])
        metadata = json.loads(Path(exported_files[0]).read_text(encoding="utf-8"))

        self.assertEqual(2, len(metadata["performers"]))
        self.assertIn("performer-group:multi", metadata["tags"])


if __name__ == "__main__":
    unittest.main()
