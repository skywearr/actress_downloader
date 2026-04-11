from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from actress_downloader.connectors.seed import SeedCatalogConnector


class SeedConnectorTests(unittest.TestCase):
    def test_alias_resolution_and_multi_performer_discovery(self) -> None:
        connector = SeedCatalogConnector(PROJECT_ROOT / "examples" / "demo_catalog.json")

        performer, candidates = connector.resolve_identity("鬼头桃菜")

        self.assertIsNotNone(performer)
        assert performer is not None
        self.assertEqual("三上悠亚", performer.canonical_name)
        self.assertEqual(1, len(candidates))

        works = connector.discover_works(performer)
        codes = {work.code for work in works}

        self.assertIn("SSIS-456", codes)
        self.assertIn("IPX-999", codes)

        multi_performer_work = next(work for work in works if work.code == "IPX-999")
        self.assertEqual(3, len(multi_performer_work.performers))


if __name__ == "__main__":
    unittest.main()
