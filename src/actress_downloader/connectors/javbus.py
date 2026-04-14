from __future__ import annotations

import html
import http.cookiejar
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, Iterable
import urllib.error
import urllib.parse
import urllib.request

from actress_downloader.alias_expander import NoOpPerformerAliasExpander, PerformerAliasExpander
from actress_downloader.connectors.base import CatalogConnectorError
from actress_downloader.domain import PerformerCredit, PerformerIdentity, WorkRecord
from actress_downloader.timing import emit_timing_event, now
from actress_downloader.utils import normalize_text


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_SEARCH_RESULT_RE = re.compile(
    r'<a class="avatar-box[^"]*" href="https?://www\.javbus\.com(?:/en)?/star/(?P<star_id>[^"]+)">'
    r'(?P<body>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_WORK_CARD_RE = re.compile(
    r'<a class="movie-box" href="https?://www\.javbus\.com(?:/en)?/(?P<code>[^"/?]+)">(?P<body>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(slots=True)
class JavbusSearchResult:
    star_id: str
    display_name: str
    avatar_url: str | None = None


@dataclass(slots=True)
class JavbusWorkCard:
    code: str
    title: str | None
    release_date: str | None
    page_url: str


class JavbusClient:
    def __init__(
        self,
        base_url: str = "https://www.javbus.com",
        english_base_url: str = "https://www.javbus.com/en",
        timeout_seconds: float = 20.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._english_base_url = english_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._opener = self._build_opener()

    def searchstar(self, query: str) -> str:
        return self._fetch_text(self.searchstar_url(query))

    def fetch_star_page(self, star_id: str, *, page: int = 1, english: bool = False) -> str:
        return self._fetch_text(self.star_url(star_id, page=page, english=english))

    def fetch_work_page(self, code: str, *, english: bool = False) -> str:
        return self._fetch_text(self.work_url(code, english=english))

    def searchstar_url(self, query: str) -> str:
        encoded = urllib.parse.quote(query.strip())
        return f"{self._english_base_url}/searchstar/{encoded}"

    def star_url(self, star_id: str, *, page: int = 1, english: bool = False) -> str:
        base = self._english_base_url if english else self._base_url
        path = f"/star/{star_id}"
        if page > 1:
            path = f"{path}/{page}"
        return f"{base}{path}"

    def work_url(self, code: str, *, english: bool = False) -> str:
        base = self._english_base_url if english else self._base_url
        return f"{base}/{code}"

    def _fetch_text(self, url: str) -> str:
        started_at = now()
        status_code: int | None = None
        body_size_bytes = 0
        error_type = ""
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout_seconds) as response:
                status_code = getattr(response, "status", None) or response.getcode()
                raw_body = response.read()
                body_size_bytes = len(raw_body)
                return raw_body.decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            error_type = type(exc).__name__
            raise CatalogConnectorError(f"JavBus request failed for {url}: HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            error_type = type(exc).__name__
            raise CatalogConnectorError(f"JavBus request failed for {url}: {exc.reason}.") from exc
        finally:
            emit_timing_event(
                "http.javbus",
                started_at,
                method="GET",
                url=url,
                status_code=status_code,
                body_size_bytes=body_size_bytes,
                error_type=error_type or None,
            )

    def _build_opener(self) -> urllib.request.OpenerDirector:
        jar = http.cookiejar.CookieJar()
        for name, value in (("existmag", "mag"), ("age", "verified"), ("dv", "1")):
            jar.set_cookie(
                http.cookiejar.Cookie(
                    version=0,
                    name=name,
                    value=value,
                    port=None,
                    port_specified=False,
                    domain="www.javbus.com",
                    domain_specified=True,
                    domain_initial_dot=False,
                    path="/",
                    path_specified=True,
                    secure=False,
                    expires=None,
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                )
            )
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


class JavbusParser:
    def parse_searchstar_results(self, html_text: str) -> list[JavbusSearchResult]:
        results: list[JavbusSearchResult] = []
        seen_star_ids: set[str] = set()
        for match in _SEARCH_RESULT_RE.finditer(html_text):
            star_id = match.group("star_id").strip()
            if not star_id or star_id in seen_star_ids:
                continue
            body = match.group("body")
            name = _extract_search_result_name(body)
            avatar_url = _extract_first_match(r'<img[^>]+src="([^"]+)"', body)
            if not name:
                continue
            results.append(JavbusSearchResult(star_id=star_id, display_name=name, avatar_url=avatar_url))
            seen_star_ids.add(star_id)
        return results

    def parse_star_name(self, html_text: str) -> str | None:
        for pattern in (
            r'<span class="pb10">(.*?)</span>',
            r'<img[^>]+src="/pics/actress/[^"]+"[^>]+title="([^"]+)"',
        ):
            value = _extract_first_match(pattern, html_text)
            if value:
                return _clean_text(value)
        title = _extract_first_match(r"<title>(.*?) - ", html_text)
        if title:
            return _clean_text(title)
        return None

    def parse_star_total_pages(self, html_text: str, star_id: str) -> int:
        page_numbers = [
            int(page_number)
            for page_number in re.findall(
                rf'/star/{re.escape(star_id)}/(\d+)',
                html_text,
                re.IGNORECASE,
            )
        ]
        return max(page_numbers, default=1)

    def parse_star_work_cards(self, html_text: str) -> list[JavbusWorkCard]:
        cards: list[JavbusWorkCard] = []
        seen_codes: set[str] = set()
        for match in _WORK_CARD_RE.finditer(html_text):
            code = match.group("code").strip()
            if not code or code in seen_codes:
                continue
            body = match.group("body")
            title = _extract_work_card_title(body)
            dates = re.findall(r"<date>(.*?)</date>", body, re.IGNORECASE | re.DOTALL)
            release_date = _clean_text(dates[1]) if len(dates) >= 2 else None
            cards.append(
                JavbusWorkCard(
                    code=code,
                    title=title,
                    release_date=release_date,
                    page_url=match.group(0).split('href="', 1)[1].split('"', 1)[0],
                )
            )
            seen_codes.add(code)
        return cards

    def parse_work_detail(self, html_text: str, *, source_url: str) -> WorkRecord:
        code = (
            _extract_first_match(r'<span[^>]*style="color:#CC0000;">\s*([A-Za-z0-9-]+)\s*</span>', html_text)
            or _extract_from_url(source_url)
        )
        if not code:
            raise CatalogConnectorError(f"Unable to parse JavBus work code from {source_url}.")

        title = (
            _extract_first_match(r'<a class="bigImage"[^>]*><img[^>]+title="([^"]*)"', html_text)
            or _extract_title_without_suffix(html_text)
        )
        release_date = _extract_first_match(r'(\d{4}-\d{2}-\d{2})', html_text)
        studio = _extract_first_match(r'href="https?://www\.javbus\.com/studio/[^"]+">([^<]+)</a>', html_text)
        series = _extract_first_match(r'href="https?://www\.javbus\.com/series/[^"]+">([^<]+)</a>', html_text)
        raw_tags = _extract_genre_tags(html_text)
        performers = [
            PerformerCredit(canonical_name=name)
            for name in _extract_star_names_from_detail(html_text)
        ]

        return WorkRecord(
            code=_clean_text(code).upper(),
            title=_clean_text(title) if title else None,
            release_date=_clean_text(release_date) if release_date else None,
            studio=_clean_text(studio) if studio else None,
            series=_clean_text(series) if series else None,
            performers=performers,
            raw_tags=raw_tags,
            source_name="javbus",
            source_url=source_url,
            extra={},
        )


@dataclass(slots=True)
class _RankedCandidate:
    star_id: str
    display_name: str
    score: float


@dataclass(slots=True)
class _AliasResolvedCandidate:
    performer: PerformerIdentity
    matched_aliases: list[str]
    score: float


class JavbusConnector:
    def __init__(
        self,
        client: JavbusClient | None = None,
        parser: JavbusParser | None = None,
        alias_expander: PerformerAliasExpander | None = None,
        candidate_confirmer: Callable[[PerformerIdentity, list[str]], bool] | None = None,
    ) -> None:
        self._client = client or JavbusClient()
        self._parser = parser or JavbusParser()
        self._alias_expander = alias_expander or NoOpPerformerAliasExpander()
        self._candidate_confirmer = candidate_confirmer
        self._star_id_by_name: dict[str, str] = {}

    def resolve_identity(
        self,
        query_name: str,
    ) -> tuple[PerformerIdentity | None, list[PerformerIdentity]]:
        query_name = query_name.strip()
        direct_star_id = self._extract_star_id(query_name)
        if direct_star_id:
            performer = self._build_identity_from_star_id(direct_star_id, query_name=query_name, confidence=1.0)
            return performer, [performer]

        initial_candidates_by_star_id = self._collect_candidates_for_query(query_name)
        ranked_candidates = self._rank_candidates(query_name, initial_candidates_by_star_id.values())
        performer_candidates = [
            PerformerIdentity(
                canonical_name=candidate.display_name,
                aliases=[],
                confidence=round(candidate.score, 3),
                source=f"javbus:star/{candidate.star_id}",
            )
            for candidate in ranked_candidates[:5]
        ]

        if len(ranked_candidates) == 1 or (
            ranked_candidates
            and
            ranked_candidates[0].score >= 0.8
            and len(ranked_candidates) > 1
            and ranked_candidates[0].score - ranked_candidates[1].score >= 0.15
        ):
            performer = self._build_identity_from_star_id(
                ranked_candidates[0].star_id,
                query_name=query_name,
                english_display_name=ranked_candidates[0].display_name,
                confidence=ranked_candidates[0].score,
            )
            return performer, [performer, *performer_candidates[1:5]]

        expanded_performer, expanded_candidates = self._resolve_via_expanded_aliases(query_name)
        if expanded_performer is not None:
            return expanded_performer, [expanded_performer, *expanded_candidates[:4]]

        merged_candidates = _merge_candidate_lists(performer_candidates, expanded_candidates)
        if merged_candidates:
            return None, merged_candidates[:5]

        if not initial_candidates_by_star_id:
            raise CatalogConnectorError(f"No JavBus performer candidates matched the query {query_name!r}.")
        return None, performer_candidates

    def _collect_candidates_for_query(self, query: str) -> dict[str, JavbusSearchResult]:
        candidates_by_star_id: dict[str, JavbusSearchResult] = {}
        for candidate in self._searchstar_candidates(query):
            candidates_by_star_id.setdefault(candidate.star_id, candidate)

        tokens = _extract_ascii_search_tokens(query)
        for token in tokens:
            if normalize_text(token) == normalize_text(query):
                continue
            for candidate in self._searchstar_candidates(token):
                candidates_by_star_id.setdefault(candidate.star_id, candidate)
        return candidates_by_star_id

    def _collect_strict_candidates_for_query(self, query: str) -> dict[str, JavbusSearchResult]:
        direct_candidates = self._searchstar_candidates(query)
        if direct_candidates:
            return {candidate.star_id: candidate for candidate in direct_candidates}

        tokens = _extract_ascii_search_tokens(query)
        if len(tokens) < 2:
            return {}

        token_candidate_sets: list[dict[str, JavbusSearchResult]] = []
        for token in tokens:
            token_candidates = {
                candidate.star_id: candidate
                for candidate in self._searchstar_candidates(token)
            }
            if not token_candidates:
                return {}
            token_candidate_sets.append(token_candidates)

        common_star_ids = set(token_candidate_sets[0].keys())
        for token_candidates in token_candidate_sets[1:]:
            common_star_ids &= set(token_candidates.keys())

        if not common_star_ids:
            return {}

        return {
            star_id: token_candidate_sets[0][star_id]
            for star_id in common_star_ids
        }

    def _searchstar_candidates(self, query: str) -> list[JavbusSearchResult]:
        try:
            html_text = self._client.searchstar(query)
        except CatalogConnectorError:
            return []
        return self._parser.parse_searchstar_results(html_text)

    def _resolve_via_expanded_aliases(
        self,
        query_name: str,
    ) -> tuple[PerformerIdentity | None, list[PerformerIdentity]]:
        alias_queries = self._alias_expander.expand_aliases(query_name)
        if not alias_queries:
            return None, []

        alias_candidate_matches: dict[str, list[str]] = {}
        alias_candidates_by_star_id: dict[str, JavbusSearchResult] = {}
        for alias_query in alias_queries:
            for candidate in self._collect_strict_candidates_for_query(alias_query).values():
                alias_candidates_by_star_id.setdefault(candidate.star_id, candidate)
                alias_candidate_matches.setdefault(candidate.star_id, [])
                if alias_query not in alias_candidate_matches[candidate.star_id]:
                    alias_candidate_matches[candidate.star_id].append(alias_query)

        if not alias_candidates_by_star_id:
            return None, []

        resolved_candidates = self._build_alias_resolved_candidates(
            query_name=query_name,
            candidates_by_star_id=alias_candidates_by_star_id,
            matched_aliases_by_star_id=alias_candidate_matches,
        )
        candidate_previews = [
            PerformerIdentity(
                canonical_name=candidate.performer.canonical_name,
                aliases=candidate.performer.aliases,
                confidence=round(candidate.score, 3),
                source=candidate.performer.source,
            )
            for candidate in resolved_candidates
        ]

        if self._candidate_confirmer is None:
            return None, candidate_previews

        for candidate in resolved_candidates:
            if self._candidate_confirmer(candidate.performer, candidate.matched_aliases):
                return candidate.performer, candidate_previews

        return None, candidate_previews

    def _build_alias_resolved_candidates(
        self,
        *,
        query_name: str,
        candidates_by_star_id: dict[str, JavbusSearchResult],
        matched_aliases_by_star_id: dict[str, list[str]],
    ) -> list[_AliasResolvedCandidate]:
        resolved: list[_AliasResolvedCandidate] = []
        for star_id, candidate in candidates_by_star_id.items():
            performer = self._build_identity_from_star_id(
                star_id,
                query_name=query_name,
                english_display_name=candidate.display_name,
                confidence=1.0,
            )
            matched_aliases = matched_aliases_by_star_id.get(star_id, [])
            performer = self._augment_identity_aliases(performer, matched_aliases)
            score = max(
                [self._score_candidate(query_name, candidate.display_name)]
                + [self._score_candidate(alias, candidate.display_name) for alias in matched_aliases]
            )
            resolved.append(
                _AliasResolvedCandidate(
                    performer=performer,
                    matched_aliases=matched_aliases,
                    score=round(score, 6),
                )
            )

        resolved.sort(
            key=lambda item: (
                len(item.matched_aliases),
                item.score,
                item.performer.canonical_name,
            ),
            reverse=True,
        )
        return resolved[:5]

    def discover_works(self, performer: PerformerIdentity) -> list[WorkRecord]:
        star_id = self._lookup_star_id(performer)
        if not star_id:
            raise CatalogConnectorError(
                f"Resolved performer {performer.canonical_name!r} is missing a JavBus star id in the current session."
            )

        page_count = self._parser.parse_star_total_pages(
            self._client.fetch_star_page(star_id, english=False),
            star_id,
        )
        work_cards_by_code: dict[str, JavbusWorkCard] = {}
        for page in range(1, page_count + 1):
            page_html = self._client.fetch_star_page(star_id, page=page, english=False)
            for work_card in self._parser.parse_star_work_cards(page_html):
                work_cards_by_code.setdefault(work_card.code, work_card)

        works: list[WorkRecord] = []
        for work_card in work_cards_by_code.values():
            work_html = self._client.fetch_work_page(work_card.code, english=False)
            works.append(
                self._parser.parse_work_detail(
                    work_html,
                    source_url=self._client.work_url(work_card.code, english=False),
                )
            )
        return works

    def _build_identity_from_star_id(
        self,
        star_id: str,
        *,
        query_name: str,
        confidence: float,
        english_display_name: str | None = None,
    ) -> PerformerIdentity:
        native_html = self._client.fetch_star_page(star_id, english=False)
        native_name = self._parser.parse_star_name(native_html)

        display_name = english_display_name
        if display_name is None:
            english_html = self._client.fetch_star_page(star_id, english=True)
            display_name = self._parser.parse_star_name(english_html)

        canonical_name = native_name or display_name or query_name
        aliases = [
            alias
            for alias in [display_name, query_name]
            if alias and normalize_text(alias) != normalize_text(canonical_name)
        ]
        performer = PerformerIdentity(
            canonical_name=canonical_name,
            aliases=_dedupe_preserve_order(aliases),
            confidence=round(confidence, 3),
            source=f"javbus:star/{star_id}",
        )
        for name in performer.all_names():
            self._star_id_by_name[normalize_text(name)] = star_id
        return performer

    def _augment_identity_aliases(
        self,
        performer: PerformerIdentity,
        aliases: list[str],
    ) -> PerformerIdentity:
        combined_aliases = _dedupe_preserve_order([*performer.aliases, *aliases])
        augmented = PerformerIdentity(
            canonical_name=performer.canonical_name,
            aliases=combined_aliases,
            confidence=performer.confidence,
            source=performer.source,
        )
        star_id = self._extract_star_id(performer.source)
        if star_id:
            for name in augmented.all_names():
                self._star_id_by_name[normalize_text(name)] = star_id
        return augmented

    def _lookup_star_id(self, performer: PerformerIdentity) -> str | None:
        for name in performer.all_names():
            star_id = self._star_id_by_name.get(normalize_text(name))
            if star_id:
                return star_id
        return self._extract_star_id(performer.source)

    def _rank_candidates(
        self,
        query_name: str,
        candidates: Iterable[JavbusSearchResult],
    ) -> list[_RankedCandidate]:
        ranked: list[_RankedCandidate] = []
        for candidate in candidates:
            score = self._score_candidate(query_name, candidate.display_name)
            ranked.append(
                _RankedCandidate(
                    star_id=candidate.star_id,
                    display_name=candidate.display_name,
                    score=score,
                )
            )

        ranked.sort(key=lambda item: (item.score, item.display_name), reverse=True)
        return ranked

    def _score_candidate(self, query_name: str, display_name: str) -> float:
        normalized_query = normalize_text(query_name)
        normalized_name = normalize_text(display_name)
        query_tokens = _extract_ascii_search_tokens(query_name)
        if query_tokens:
            token_hits = sum(1 for token in query_tokens if token in normalized_name)
            coverage = token_hits / max(1, len(query_tokens))
        else:
            coverage = 1.0 if normalized_query == normalized_name else 0.0
        ratio = SequenceMatcher(None, normalized_query, normalized_name).ratio()
        ordered_ratio = max(
            ratio,
            SequenceMatcher(None, normalized_query, " ".join(reversed(normalized_name.split()))).ratio(),
        )
        return round(coverage * 0.7 + ordered_ratio * 0.3, 6)

    @staticmethod
    def _extract_star_id(value: str) -> str | None:
        match = re.search(r"/star/([A-Za-z0-9_-]+)", value)
        if match:
            return match.group(1)
        normalized = value.strip()
        if re.fullmatch(r"javbus:star/[A-Za-z0-9_-]+", normalized):
            return normalized.rsplit("/", 1)[-1]
        return None


def _extract_ascii_search_tokens(value: str) -> list[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9*]+", value)
        if len(token) >= 2
    ]
    return _dedupe_preserve_order(tokens)


def _extract_search_result_name(body: str) -> str | None:
    for pattern in (
        r'<span class="mleft">(.*?)<button',
        r'<img[^>]+title="([^"]+)"',
    ):
        value = _extract_first_match(pattern, body)
        if value:
            return _clean_text(value)
    return None


def _extract_work_card_title(body: str) -> str | None:
    value = _extract_first_match(r'<span>(.*?)<br', body)
    if not value:
        value = _extract_first_match(r'<img[^>]+title="([^"]*)"', body)
    cleaned = _clean_text(value) if value else None
    return cleaned or None


def _extract_title_without_suffix(html_text: str) -> str | None:
    title = _extract_first_match(r"<title>(.*?)</title>", html_text)
    if not title:
        return None
    return _clean_text(title.split(" - ", 1)[0])


def _extract_labeled_value(html_text: str, label: str) -> str | None:
    return _extract_first_match(
        rf'<span class="header">{re.escape(label)}:</span>\s*(?:<span[^>]*>)?(.*?)(?:</span>|</p>)',
        html_text,
    )


def _extract_labeled_link_text(html_text: str, label: str) -> str | None:
    return _extract_first_match(
        rf'<span class="header">{re.escape(label)}:</span>\s*<a[^>]*>(.*?)</a>',
        html_text,
    )


def _extract_genre_tags(html_text: str) -> list[str]:
    tags = [
        _clean_text(tag)
        for tag in re.findall(
            r'href="https?://www\.javbus\.com/genre/[^"]+">([^<]+?)(?:</a>|/a>)',
            html_text,
            re.IGNORECASE,
        )
    ]
    return _dedupe_preserve_order([tag for tag in tags if tag])


def _extract_star_names_from_detail(html_text: str) -> list[str]:
    start = html_text.find('<p class="star-show"')
    end = html_text.find('<div id="star-div">', start) if start >= 0 else -1
    if start < 0:
        return []
    star_block = html_text[start:end] if end > start else html_text[start:]
    names = [
        _clean_text(name)
        for name in re.findall(
            r'href="https?://www\.javbus\.com/star/[^"]+"[^>]*>([^<]+)</a>',
            star_block,
            re.IGNORECASE,
        )
    ]
    return _dedupe_preserve_order([name for name in names if name])


def _extract_from_url(source_url: str) -> str | None:
    match = re.search(r"/([A-Za-z0-9-]+)$", source_url)
    if match:
        return match.group(1)
    return None


def _extract_first_match(pattern: str, value: str) -> str | None:
    match = re.search(pattern, value, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _clean_text(match.group(1))


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    normalized = _WHITESPACE_RE.sub(" ", without_tags).strip()
    return normalized


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(value)
    return deduped


def _merge_candidate_lists(
    primary: list[PerformerIdentity],
    secondary: list[PerformerIdentity],
) -> list[PerformerIdentity]:
    merged: list[PerformerIdentity] = []
    seen_sources: set[str] = set()
    for candidate in [*primary, *secondary]:
        source_key = candidate.source or normalize_text(candidate.canonical_name)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        merged.append(candidate)
    return merged
