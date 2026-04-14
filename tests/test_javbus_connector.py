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
        <img src="/pics/actress/ghi_a.jpg" title="Mikami Riho">
      </div>
      <div class="photo-info">
        <span class="mleft">Mikami Riho<button class="btn btn-xs btn-info" disabled="disabled">Censored</button></span>
      </div>
    </a>
  </div>
</div>
"""

SEARCHSTAR_DIRECT_CJK_HTML = """
<div id="waterfall">
  <div class="item">
    <a class="avatar-box text-center" href="https://www.javbus.com/star/abc">
      <div class="photo-frame">
        <img src="/pics/actress/abc_a.jpg" title="娑撳绗傞幃鐘辩盎">
      </div>
      <div class="photo-info">
        <span class="mleft">娑撳绗傞幃鐘辩盎<button class="btn btn-xs btn-info" disabled="disabled">Censored</button></span>
      </div>
    </a>
  </div>
</div>
"""

STAR_ZH_PAGE_1 = """
<title>娑撳绗傞幃鐘辩盎 - 婵傚啿鍔?- 瑜拌京澧?/title>
<div class="avatar-box">
  <div class="photo-frame">
    <img src="/pics/actress/abc_a.jpg" title="娑撳绗傞幃鐘辩盎">
  </div>
  <div class="photo-info">
    <span class="pb10">娑撳绗傞幃鐘辩盎</span>
  </div>
</div>
<div id="waterfall">
  <div class="item">
    <a class="movie-box" href="https://www.javbus.com/SSIS-001">
      <div class="photo-info">
        <span>缁楊兛绔撮柈銊ょ稊閸?br />
          <div class="item-tag"></div>
          <date>SSIS-001</date> / <date>2024-01-02</date>
        </span>
      </div>
    </a>
  </div>
</div>
<div class="text-center hidden-xs">
  <ul class="pagination pagination-lg">
    <li class="active"><a href="/star/abc/1">1</a></li>
    <li><a href="/star/abc/2">2</a></li>
    <li><a id="next" href="/star/abc/2"></a></li>
  </ul>
</div>
"""

STAR_ZH_PAGE_2 = """
<title>娑撳绗傞幃鐘辩盎 - 婵傚啿鍔?- 瑜拌京澧?/title>
<div id="waterfall">
  <div class="item">
    <a class="movie-box" href="https://www.javbus.com/SSIS-002">
      <div class="photo-info">
        <span>缁楊兛绨╅柈銊ょ稊閸?br />
          <div class="item-tag"></div>
          <date>SSIS-002</date> / <date>2024-02-03</date>
        </span>
      </div>
    </a>
  </div>
</div>
"""

WORK_DETAIL_1 = """
<title>缁楊兛绔撮柈銊ょ稊閸?- JavBus</title>
<a class="bigImage" href="/pics/cover/a.jpg"><img src="/pics/cover/a.jpg" title="缁楊兛绔撮柈銊ょ稊閸?"></a>
<div class="info">
  <p><span class="header">鐠€妯哄灳绾?</span> <span style="color:#CC0000;">SSIS-001</span></p>
  <p><span class="header">閻ц壈顢戦弮銉︽埂:</span> 2024-01-02</p>
  <p><span class="header">鐟佹垝缍旈崯?</span> <a href="https://www.javbus.com/studio/s1">S1</a></p>
  <p><span class="header">缁鍨?</span> <a href="https://www.javbus.com/series/x1">Series One</a></p>
  <p class="header">妞ょ偛鍨?<span id="genre-toggle"></span></p>
  <p>
    <span class="genre"><label><input type="checkbox"><a href="https://www.javbus.com/genre/4o">妤傛鏆欑挬?/a></label></span>
    <span class="genre"><label><input type="checkbox"><a href="https://www.javbus.com/genre/f">閸狀噣鐝ㄦ担婊冩惂</a></label></span>
  </p>
  <p class="star-show"><span class="header">濠曟柨鎽?/span>:<span id="star-toggle"></span></p>
  <ul>
    <div class="star-box">
      <li><a href="https://www.javbus.com/star/abc"><img src="/pics/actress/abc_a.jpg" title="娑撳绗傞幃鐘辩盎"></a></li>
      <div class="star-name"><a href="https://www.javbus.com/star/abc" title="娑撳绗傞幃鐘辩盎">娑撳绗傞幃鐘辩盎</a></div>
    </div>
  </ul>
</div>
<div id="star-div"></div>
"""

WORK_DETAIL_2 = """
<title>缁楊兛绨╅柈銊ょ稊閸?- JavBus</title>
<a class="bigImage" href="/pics/cover/b.jpg"><img src="/pics/cover/b.jpg" title="缁楊兛绨╅柈銊ょ稊閸?"></a>
<div class="info">
  <p><span class="header">鐠€妯哄灳绾?</span> <span style="color:#CC0000;">SSIS-002</span></p>
  <p><span class="header">閻ц壈顢戦弮銉︽埂:</span> 2024-02-03</p>
  <p><span class="header">鐟佹垝缍旈崯?</span> <a href="https://www.javbus.com/studio/s1">S1</a></p>
  <p class="header">妞ょ偛鍨?<span id="genre-toggle"></span></p>
  <p>
    <span class="genre"><label><input type="checkbox"><a href="https://www.javbus.com/genre/13">閹存劗鍟涢惃鍕偝娴?/a></label></span>
  </p>
  <p class="star-show"><span class="header">濠曟柨鎽?/span>:<span id="star-toggle"></span></p>
  <ul>
    <div class="star-box">
      <li><a href="https://www.javbus.com/star/abc"><img src="/pics/actress/abc_a.jpg" title="娑撳绗傞幃鐘辩盎"></a></li>
      <div class="star-name"><a href="https://www.javbus.com/star/abc" title="娑撳绗傞幃鐘辩盎">娑撳绗傞幃鐘辩盎</a></div>
    </div>
    <div class="star-box">
      <li><a href="https://www.javbus.com/star/zzz"><img src="/pics/actress/zzz_a.jpg" title="濮楀婀伴妵鍌樺€為妵?"></a></li>
      <div class="star-name"><a href="https://www.javbus.com/star/zzz" title="濮楀婀伴妵鍌樺€為妵?">濮楀婀伴妵鍌樺€為妵?</a></div>
    </div>
  </ul>
</div>
<div id="star-div"></div>
"""


class FakeJavbusClient:
    def searchstar(self, query: str) -> str:
        key = query.lower()
        if query == "涓変笂鎮犱簻":
            return SEARCHSTAR_DIRECT_CJK_HTML
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
        if english:
            return '<div class="avatar-box"><span class="pb10">Mikami Yua</span></div>'
        if page == 1:
            return STAR_ZH_PAGE_1
        if page == 2:
            return STAR_ZH_PAGE_2
        raise AssertionError(f"unexpected page: {page}")

    def fetch_work_page(self, code: str, *, english: bool = False) -> str:
        if english:
            raise AssertionError("work pages should be fetched from zh pages in this test")
        if code == "SSIS-001":
            return WORK_DETAIL_1
        if code == "SSIS-002":
            return WORK_DETAIL_2
        raise AssertionError(f"unexpected work code: {code}")

    def work_url(self, code: str, *, english: bool = False) -> str:
        prefix = "https://www.javbus.com/en" if english else "https://www.javbus.com"
        return f"{prefix}/{code}"


class FakeAliasExpander:
    def __init__(self, aliases_by_query: dict[str, list[str]]) -> None:
        self._aliases_by_query = aliases_by_query

    def expand_aliases(self, query_name: str) -> list[str]:
        return list(self._aliases_by_query.get(query_name, []))


class JavbusParserTests(unittest.TestCase):
    def test_parses_searchstar_results(self) -> None:
        parser = JavbusParser()

        results = parser.parse_searchstar_results(SEARCHSTAR_YUA_HTML)

        self.assertEqual(["abc", "def"], [result.star_id for result in results])
        self.assertEqual(["Mikami Yua", "Imai Yua"], [result.display_name for result in results])

    def test_parses_star_page_and_work_detail(self) -> None:
        parser = JavbusParser()

        self.assertEqual("娑撳绗傞幃鐘辩盎", parser.parse_star_name(STAR_ZH_PAGE_1))
        self.assertEqual(2, parser.parse_star_total_pages(STAR_ZH_PAGE_1, "abc"))
        work_cards = parser.parse_star_work_cards(STAR_ZH_PAGE_1)
        self.assertEqual(["SSIS-001"], [card.code for card in work_cards])

        work = parser.parse_work_detail(WORK_DETAIL_2, source_url="https://www.javbus.com/SSIS-002")
        self.assertEqual("SSIS-002", work.code)
        self.assertEqual("缁楊兛绨╅柈銊ょ稊閸?", work.title)
        self.assertEqual("2024-02-03", work.release_date)
        self.assertEqual("S1", work.studio)
        self.assertEqual(["閹存劗鍟涢惃鍕偝娴?"], work.raw_tags)
        self.assertEqual(["娑撳绗傞幃鐘辩盎", "濮楀婀伴妵鍌樺€為妵?"], [credit.canonical_name for credit in work.performers])


class JavbusConnectorTests(unittest.TestCase):
    def test_resolves_identity_from_tokenized_english_query(self) -> None:
        connector = JavbusConnector(client=FakeJavbusClient(), parser=JavbusParser())

        performer, candidates = connector.resolve_identity("Yua Mikami")

        self.assertIsNotNone(performer)
        assert performer is not None
        self.assertEqual("娑撳绗傞幃鐘辩盎", performer.canonical_name)
        self.assertIn("Mikami Yua", performer.aliases)
        self.assertEqual("javbus:star/abc", performer.source)
        self.assertGreaterEqual(performer.confidence, 0.8)
        self.assertEqual("娑撳绗傞幃鐘辩盎", candidates[0].canonical_name)

    def test_discovers_multi_page_works_for_resolved_performer(self) -> None:
        connector = JavbusConnector(client=FakeJavbusClient(), parser=JavbusParser())
        performer, _ = connector.resolve_identity("Yua Mikami")
        assert performer is not None

        works = connector.discover_works(performer)

        self.assertEqual(["SSIS-001", "SSIS-002"], [work.code for work in works])
        self.assertEqual(2, len(works[1].performers))

    def test_resolves_identity_from_direct_non_latin_query(self) -> None:
        connector = JavbusConnector(client=FakeJavbusClient(), parser=JavbusParser())

        performer, candidates = connector.resolve_identity("涓変笂鎮犱簻")

        self.assertIsNotNone(performer)
        assert performer is not None
        self.assertEqual("娑撳绗傞幃鐘辩盎", performer.canonical_name)
        self.assertEqual("javbus:star/abc", performer.source)
        self.assertEqual("娑撳绗傞幃鐘辩盎", candidates[0].canonical_name)

    def test_resolves_identity_from_llm_alias_after_confirmation(self) -> None:
        seen_prompts: list[tuple[str, list[str]]] = []

        def confirmer(performer, matched_aliases):
            seen_prompts.append((performer.canonical_name, matched_aliases))
            return True

        connector = JavbusConnector(
            client=FakeJavbusClient(),
            parser=JavbusParser(),
            alias_expander=FakeAliasExpander({"Ghost Alias": ["涓変笂鎮犱簻"]}),
            candidate_confirmer=confirmer,
        )

        performer, candidates = connector.resolve_identity("Ghost Alias")

        self.assertIsNotNone(performer)
        assert performer is not None
        self.assertEqual("娑撳绗傞幃鐘辩盎", performer.canonical_name)
        self.assertIn("Ghost Alias", performer.aliases)
        self.assertIn("涓変笂鎮犱簻", performer.aliases)
        self.assertEqual([("娑撳绗傞幃鐘辩盎", ["涓変笂鎮犱簻"])], seen_prompts)
        self.assertEqual("娑撳绗傞幃鐘辩盎", candidates[0].canonical_name)

    def test_returns_candidates_when_all_alias_candidates_are_rejected(self) -> None:
        connector = JavbusConnector(
            client=FakeJavbusClient(),
            parser=JavbusParser(),
            alias_expander=FakeAliasExpander({"Ghost Alias": ["涓変笂鎮犱簻"]}),
            candidate_confirmer=lambda performer, matched_aliases: False,
        )

        performer, candidates = connector.resolve_identity("Ghost Alias")

        self.assertIsNone(performer)
        self.assertGreaterEqual(len(candidates), 1)
        self.assertEqual("javbus:star/abc", candidates[0].source)
        self.assertIn("Ghost Alias", candidates[0].aliases)
        self.assertIn("涓変笂鎮犱簻", candidates[0].aliases)


if __name__ == "__main__":
    unittest.main()
