from __future__ import annotations

from actress_downloader.connectors.base import CatalogConnector, CatalogConnectorError
from actress_downloader.domain import PipelineResult
from actress_downloader.graph import build_catalog_graph
from actress_downloader.sidecar import SidecarExporter
from actress_downloader.storage import CatalogRepository
from actress_downloader.tagging import TaggingService


def run_linear_pipeline(
    query_name: str,
    connector: CatalogConnector,
    repository: CatalogRepository,
    exporter: SidecarExporter,
    tagger: TaggingService,
) -> PipelineResult:
    try:
        performer, candidates = connector.resolve_identity(query_name)
    except CatalogConnectorError as exc:
        return PipelineResult(
            query_name=query_name,
            performer=None,
            performer_candidates=[],
            review_required=True,
            errors=[str(exc)],
        )

    if performer is None:
        return PipelineResult(
            query_name=query_name,
            performer=None,
            performer_candidates=candidates,
            review_required=True,
            errors=[
                "Unable to uniquely resolve performer identity. Manual review is required."
            ],
        )

    repository.initialize()
    try:
        works = connector.discover_works(performer)
    except CatalogConnectorError as exc:
        return PipelineResult(
            query_name=query_name,
            performer=performer,
            performer_candidates=candidates,
            review_required=True,
            errors=[str(exc)],
        )
    tagged_works = tagger.tag_works(works)
    repository.persist_works(tagged_works)
    exported_files = exporter.export_works(tagged_works)
    return PipelineResult(
        query_name=query_name,
        performer=performer,
        performer_candidates=candidates,
        works=tagged_works,
        exported_files=exported_files,
        review_required=False,
        errors=[],
    )


def run_catalog_pipeline(
    query_name: str,
    connector: CatalogConnector,
    repository: CatalogRepository,
    exporter: SidecarExporter,
    tagger: TaggingService,
) -> PipelineResult:
    try:
        graph = build_catalog_graph(
            connector=connector,
            repository=repository,
            exporter=exporter,
            tagger=tagger,
        )
    except RuntimeError:
        return run_linear_pipeline(
            query_name=query_name,
            connector=connector,
            repository=repository,
            exporter=exporter,
            tagger=tagger,
        )

    state = graph.invoke({"query_name": query_name})
    return PipelineResult(
        query_name=query_name,
        performer=state.get("performer"),
        performer_candidates=state.get("performer_candidates", []),
        works=state.get("works", []),
        exported_files=state.get("exported_files", []),
        review_required=state.get("review_required", False),
        errors=state.get("errors", []),
    )
