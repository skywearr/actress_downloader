from __future__ import annotations

from copy import deepcopy
import logging

from actress_downloader.domain import WorkRecord
from actress_downloader.llm import NoOpWorkTagLLM, WorkTagLLM
from actress_downloader.utils import extract_year, normalize_tag


logger = logging.getLogger(__name__)


class RuleBasedTagger:
    """Generate stable structural tags before optional LLM enrichment."""

    def generate_tags(self, work: WorkRecord) -> list[str]:
        tags = {normalize_tag(tag) for tag in work.raw_tags if tag}
        performer_count = len(work.performers)

        tags.add("performer-group:solo" if performer_count <= 1 else "performer-group:multi")
        tags.add(f"performer-count:{performer_count}")

        if work.studio:
            tags.add(f"studio:{normalize_tag(work.studio)}")

        if work.series:
            tags.add(f"series:{normalize_tag(work.series)}")

        year = extract_year(work.release_date)
        if year:
            tags.add(f"year:{year}")

        return sorted(tag for tag in tags if tag)


class TaggingService:
    def __init__(
        self,
        rule_tagger: RuleBasedTagger | None = None,
        llm_tagger: WorkTagLLM | None = None,
    ) -> None:
        self._rule_tagger = rule_tagger or RuleBasedTagger()
        self._llm_tagger = llm_tagger or NoOpWorkTagLLM()

    def tag_work(self, work: WorkRecord) -> WorkRecord:
        tagged_work = deepcopy(work)
        rule_tags = self._rule_tagger.generate_tags(tagged_work)
        try:
            llm_tags = [
                normalize_tag(tag)
                for tag in self._llm_tagger.generate_tags(tagged_work, rule_tags)
            ]
        except Exception as exc:
            # LLM enrichment is best-effort; keep the pipeline alive with rule tags.
            logger.warning("LLM tag enrichment failed for %s: %s", tagged_work.code, exc)
            llm_tags = []
        tagged_work.tags = sorted({*rule_tags, *(tag for tag in llm_tags if tag)})
        return tagged_work

    def tag_works(self, works: list[WorkRecord]) -> list[WorkRecord]:
        return [self.tag_work(work) for work in works]
