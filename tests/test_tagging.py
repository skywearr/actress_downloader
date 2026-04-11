from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from actress_downloader.domain import PerformerCredit, WorkRecord
from actress_downloader.tagging import TaggingService


class FailingLLM:
    def generate_tags(self, work: WorkRecord, existing_tags: list[str]) -> list[str]:
        raise RuntimeError("rate limited")


class TaggingTests(unittest.TestCase):
    def test_llm_failure_falls_back_to_rule_tags(self) -> None:
        service = TaggingService(llm_tagger=FailingLLM())
        work = WorkRecord(
            code="TEST-429",
            title="Fallback Test",
            release_date="2025-01-19",
            studio="IDEA POCKET",
            performers=[PerformerCredit(canonical_name="三上悠亚")],
            raw_tags=["HD"],
        )

        tagged = service.tag_work(work)

        self.assertIn("performer-group:solo", tagged.tags)
        self.assertIn("studio:idea-pocket", tagged.tags)
        self.assertIn("year:2025", tagged.tags)


if __name__ == "__main__":
    unittest.main()
