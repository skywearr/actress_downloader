from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from actress_downloader.storage import normalize_release_date


class StorageDateTests(unittest.TestCase):
    def test_keeps_valid_iso_dates(self) -> None:
        self.assertEqual("2024-01-19", normalize_release_date("2024-01-19"))

    def test_drops_all_zero_dates(self) -> None:
        self.assertIsNone(normalize_release_date("0000-00-00"))

    def test_drops_invalid_calendar_dates(self) -> None:
        self.assertIsNone(normalize_release_date("2024-00-00"))
        self.assertIsNone(normalize_release_date("2024-13-01"))
        self.assertIsNone(normalize_release_date("2024-02-31"))

    def test_drops_empty_values(self) -> None:
        self.assertIsNone(normalize_release_date(None))
        self.assertIsNone(normalize_release_date(""))
        self.assertIsNone(normalize_release_date("   "))


if __name__ == "__main__":
    unittest.main()
