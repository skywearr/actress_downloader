from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from actress_downloader.connectors.base import CatalogConnectorError
from actress_downloader.connectors.javbus import JavbusConnector, JavbusParser


SEARCHSTAR_YUA_HTML = """
<div id="waterfall">
  <div class="item">
    <a class="avatar-box text-center" href="https://www.javbus.com/en/star/abc">
      <div class="photo-frame">
        <img src="/pics/actress/abc_a.jpg" title="Mikami Yua">
      </div>
      <div class="photo-info">
        <span class="mleft">Mikami Yua<button class="btn btn-xs btn-info" disabled="disabled">Censored</button></span>
      </div>
    </a>
  </div>
  <div class="item">
    <a class="avatar-box text-center" href="https://www.javbus.com/en/star/def">
      <div class="photo-frame">
        <img src="/pics/actress/def_a.jpg" title="Imai Yua">
      </div>
      <div class="photo-info">
        <span class="mleft">Imai Yua<button class="btn btn-xs btn-info" disabled="disabled">Censored</button></span>
      </div>
    </a>
  </div>
</div>
"""

SEARCHSTAR_MIKAMI_HTML = """
<div id="waterfall">
  <div class="item">
    <a class="avatar-box text-center" href="https://www.javbus.com/en/star/abc">
      <div class="photo-frame">
        <img src="/pics/actress/abc_a.jpg" title="Mikami Yua">
      </div>
      <div class="photo-info">
        <span class="mleft">Mikami Yua<button class="btn btn-xs btn-info" disabled="disabled">Censored</button></span>
      </div>
    </a>
  </div>
  <div class="item">
    <a class="avatar-box text-center" href="https://www.javbus.com/en/star/ghi">
      <div class="photo-frame">
        <img src="/pics/actress/ghi_a.jpg" title="Aya Mikami">
      </div>
      <div class="photo-info">
        <span class="mleft">Aya Mikami<button class="btn btn-xs btn-info" disabled="disabled">Censored</button></span>
      </div>
    </a>
  </div>
</div>
"""

STAR_NATIVE_HTML = '<div class="avatar-box"><span class="pb10">Native ABC</span></div>'
STAR_ENGLISH_HTML = '<div class="avatar-box"><span class="pb10">Mikami Yua</span></div>'


class FakeJavbusClient:
    def searchstar(self, query: str) -> str:
        key = query.lower()
        if key == "ghost alias":
            raise CatalogConnectorError("no direct match")
        if key == "yua":
            return SEARCHSTAR_YUA_HTML
        if key == "mikami":
            return SEARCHSTAR_MIKAMI_HTML
        raise CatalogConnectorError(f"unexpected search query: {query}")

    def fetch_star_page(self, star_id: str, *, page: int = 1, english: bool = False) -> str:
        if star_id != "abc":
            raise AssertionError(f"unexpected star id: {star_id}")
        return STAR_ENGLISH_HTML if english else STAR_NATIVE_HTML

    def fetch_work_page(self, code: str, *, english: bool = False) -> str:
        raise AssertionError("not used in this test")

    def work_url(self, code: str, *, english: bool = False) -> str:
        raise AssertionError("not used in this test")


class FakeAliasExpander:
    def expand_aliases(self, query_name: str) -> list[str]:
        if query_name == "Ghost Alias":
            return ["Yua Mikami", "Mikami Yua"]
        return []


class JavbusAliasResolutionTests(unittest.TestCase):
    def test_alias_queries_use_strict_token_intersection(self) -> None:
        seen_prompts: list[tuple[str, list[str]]] = []

        def confirmer(performer, matched_aliases):
            seen_prompts.append((performer.source, matched_aliases))
            return False

        connector = JavbusConnector(
            client=FakeJavbusClient(),
            parser=JavbusParser(),
            alias_expander=FakeAliasExpander(),
            candidate_confirmer=confirmer,
        )

        performer, candidates = connector.resolve_identity("Ghost Alias")

        self.assertIsNone(performer)
        self.assertEqual(1, len(candidates))
        self.assertEqual("javbus:star/abc", candidates[0].source)
        self.assertEqual(
            [("javbus:star/abc", ["Yua Mikami", "Mikami Yua"])],
            seen_prompts,
        )
        self.assertIn("Ghost Alias", candidates[0].aliases)
        self.assertIn("Yua Mikami", candidates[0].aliases)
        self.assertIn("Mikami Yua", candidates[0].aliases)


if __name__ == "__main__":
    unittest.main()
