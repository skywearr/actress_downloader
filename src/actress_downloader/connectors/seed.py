from __future__ import annotations

import copy
import difflib
import json
from pathlib import Path

from actress_downloader.connectors.base import CatalogConnector
from actress_downloader.domain import PerformerCredit, PerformerIdentity, WorkRecord
from actress_downloader.utils import normalize_text


class SeedCatalogConnector(CatalogConnector):
    """Offline connector backed by a local JSON file for MVP development."""

    def __init__(self, seed_path: Path) -> None:
        self._seed_path = seed_path
        self._performers: dict[str, PerformerIdentity] = {}
        self._alias_index: dict[str, list[PerformerIdentity]] = {}
        self._works: list[WorkRecord] = []
        self._load()

    def _load(self) -> None:
        payload = json.loads(self._seed_path.read_text(encoding="utf-8"))

        for performer_payload in payload.get("performers", []):
            performer = PerformerIdentity(
                canonical_name=performer_payload["canonical_name"],
                aliases=performer_payload.get("aliases", []),
                confidence=1.0,
                source="seed",
            )
            self._performers[performer.canonical_name] = performer
            for name in performer.all_names():
                key = normalize_text(name)
                self._alias_index.setdefault(key, []).append(performer)

        for work_payload in payload.get("works", []):
            performers: list[PerformerCredit] = []
            for performer_name in work_payload.get("performers", []):
                identity = self._performers.get(performer_name)
                if identity is None:
                    identity = PerformerIdentity(canonical_name=performer_name, source="seed")
                    self._performers[identity.canonical_name] = identity
                    self._alias_index.setdefault(normalize_text(identity.canonical_name), []).append(identity)
                performers.append(
                    PerformerCredit(
                        canonical_name=identity.canonical_name,
                        aliases=identity.aliases,
                    )
                )

            self._works.append(
                WorkRecord(
                    code=work_payload["code"],
                    title=work_payload.get("title"),
                    release_date=work_payload.get("release_date"),
                    studio=work_payload.get("studio"),
                    series=work_payload.get("series"),
                    performers=performers,
                    raw_tags=work_payload.get("raw_tags", []),
                    source_name=work_payload.get("source_name", "seed"),
                    source_url=work_payload.get("source_url"),
                    synopsis=work_payload.get("synopsis"),
                    extra=work_payload.get("extra", {}),
                )
            )

    def resolve_identity(
        self,
        query_name: str,
    ) -> tuple[PerformerIdentity | None, list[PerformerIdentity]]:
        normalized_query = normalize_text(query_name)
        exact_matches = self._dedupe_performers(self._alias_index.get(normalized_query, []))
        if len(exact_matches) == 1:
            performer = copy.deepcopy(exact_matches[0])
            performer.confidence = 1.0
            return performer, [copy.deepcopy(match) for match in exact_matches]
        if len(exact_matches) > 1:
            return None, [copy.deepcopy(match) for match in exact_matches]

        scored_candidates: list[tuple[float, PerformerIdentity]] = []
        for performer in self._performers.values():
            score = max(
                difflib.SequenceMatcher(None, normalized_query, normalize_text(name)).ratio()
                for name in performer.all_names()
            )
            if score >= 0.6:
                scored_candidates.append((score, performer))

        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        if not scored_candidates:
            return None, []

        top_score, top_candidate = scored_candidates[0]
        candidates = [candidate for _, candidate in scored_candidates[:5]]
        if len(scored_candidates) > 1 and abs(top_score - scored_candidates[1][0]) < 0.05:
            return None, [copy.deepcopy(candidate) for candidate in self._dedupe_performers(candidates)]

        performer = copy.deepcopy(top_candidate)
        performer.confidence = round(top_score, 3)
        return performer, [copy.deepcopy(candidate) for candidate in self._dedupe_performers(candidates)]

    def discover_works(self, performer: PerformerIdentity) -> list[WorkRecord]:
        target_names = {normalize_text(name) for name in performer.all_names()}
        matched_works: list[WorkRecord] = []
        for work in self._works:
            work_names = {
                normalize_text(name)
                for credit in work.performers
                for name in [credit.canonical_name, *credit.aliases]
            }
            if target_names.intersection(work_names):
                matched_works.append(copy.deepcopy(work))
        return matched_works

    @staticmethod
    def _dedupe_performers(performers: list[PerformerIdentity]) -> list[PerformerIdentity]:
        deduped: list[PerformerIdentity] = []
        seen: set[str] = set()
        for performer in performers:
            if performer.canonical_name in seen:
                continue
            deduped.append(performer)
            seen.add(performer.canonical_name)
        return deduped
