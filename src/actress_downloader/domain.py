from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class PerformerIdentity:
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = ""

    def all_names(self) -> list[str]:
        names: list[str] = [self.canonical_name, *self.aliases]
        deduped: list[str] = []
        for name in names:
            if name and name not in deduped:
                deduped.append(name)
        return deduped


@dataclass(slots=True)
class PerformerCredit:
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    role: str = "performer"

    def to_identity(self) -> PerformerIdentity:
        return PerformerIdentity(canonical_name=self.canonical_name, aliases=self.aliases)


@dataclass(slots=True)
class WorkRecord:
    code: str
    title: str | None = None
    release_date: str | None = None
    studio: str | None = None
    series: str | None = None
    performers: list[PerformerCredit] = field(default_factory=list)
    raw_tags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_name: str = ""
    source_url: str | None = None
    synopsis: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PipelineResult:
    query_name: str
    performer: PerformerIdentity | None
    performer_candidates: list[PerformerIdentity] = field(default_factory=list)
    works: list[WorkRecord] = field(default_factory=list)
    exported_files: list[str] = field(default_factory=list)
    review_required: bool = False
    errors: list[str] = field(default_factory=list)
