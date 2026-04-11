from __future__ import annotations

from typing import Protocol

from actress_downloader.domain import PerformerIdentity, WorkRecord


class CatalogConnector(Protocol):
    def resolve_identity(
        self,
        query_name: str,
    ) -> tuple[PerformerIdentity | None, list[PerformerIdentity]]:
        """Resolve an input name into a canonical performer identity."""

    def discover_works(self, performer: PerformerIdentity) -> list[WorkRecord]:
        """Return all known works for a resolved performer."""
