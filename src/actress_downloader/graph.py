from __future__ import annotations

from typing import Any, TypedDict

from actress_downloader.connectors.base import CatalogConnector, CatalogConnectorError
from actress_downloader.domain import PerformerIdentity, WorkRecord
from actress_downloader.sidecar import SidecarExporter
from actress_downloader.storage import CatalogRepository
from actress_downloader.tagging import TaggingService


class CatalogGraphState(TypedDict, total=False):
    query_name: str
    performer: PerformerIdentity | None
    performer_candidates: list[PerformerIdentity]
    review_required: bool
    works: list[WorkRecord]
    exported_files: list[str]
    errors: list[str]


def build_catalog_graph(
    connector: CatalogConnector,
    repository: CatalogRepository,
    exporter: SidecarExporter,
    tagger: TaggingService,
) -> Any:
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "LangGraph is not installed. Run `pip install -e .` before invoking the graph pipeline."
        ) from exc

    def normalize_input(state: CatalogGraphState) -> CatalogGraphState:
        return {
            "query_name": state["query_name"].strip(),
            "errors": [],
        }

    def resolve_identity(state: CatalogGraphState) -> CatalogGraphState:
        errors = list(state.get("errors", []))
        try:
            performer, candidates = connector.resolve_identity(state["query_name"])
        except CatalogConnectorError as exc:
            errors.append(str(exc))
            return {
                "performer": None,
                "performer_candidates": [],
                "review_required": True,
                "errors": errors,
            }
        review_required = performer is None
        if performer is None:
            if candidates:
                errors.append("Multiple performer candidates found; manual review is required.")
            else:
                errors.append("No performer candidate matched the query.")
        return {
            "performer": performer,
            "performer_candidates": candidates,
            "review_required": review_required,
            "errors": errors,
        }

    def discover_works(state: CatalogGraphState) -> CatalogGraphState:
        performer = state.get("performer")
        if performer is None:
            return {"works": []}
        try:
            works = connector.discover_works(performer)
        except CatalogConnectorError as exc:
            errors = list(state.get("errors", []))
            errors.append(str(exc))
            return {
                "works": [],
                "review_required": True,
                "errors": errors,
            }
        return {"works": works}

    def tag_works(state: CatalogGraphState) -> CatalogGraphState:
        tagged_works = tagger.tag_works(state.get("works", []))
        return {"works": tagged_works}

    def persist_works(state: CatalogGraphState) -> CatalogGraphState:
        repository.initialize()
        repository.persist_works(state.get("works", []))
        return {}

    def export_sidecars(state: CatalogGraphState) -> CatalogGraphState:
        exported_files = exporter.export_works(state.get("works", []))
        return {"exported_files": exported_files}

    def review_required_route(state: CatalogGraphState) -> str:
        return "review_required" if state.get("review_required", False) else "discover_works"

    def discover_route(state: CatalogGraphState) -> str:
        return "review_required" if state.get("review_required", False) else "tag_works"

    def review_required(state: CatalogGraphState) -> CatalogGraphState:
        return state

    graph = StateGraph(CatalogGraphState)
    graph.add_node("normalize_input", normalize_input)
    graph.add_node("resolve_identity", resolve_identity)
    graph.add_node("review_required", review_required)
    graph.add_node("discover_works", discover_works)
    graph.add_node("tag_works", tag_works)
    graph.add_node("persist_works", persist_works)
    graph.add_node("export_sidecars", export_sidecars)

    graph.add_edge(START, "normalize_input")
    graph.add_edge("normalize_input", "resolve_identity")
    graph.add_conditional_edges(
        "resolve_identity",
        review_required_route,
        {
            "review_required": "review_required",
            "discover_works": "discover_works",
        },
    )
    graph.add_edge("review_required", END)
    graph.add_conditional_edges(
        "discover_works",
        discover_route,
        {
            "review_required": "review_required",
            "tag_works": "tag_works",
        },
    )
    graph.add_edge("tag_works", "persist_works")
    graph.add_edge("persist_works", "export_sidecars")
    graph.add_edge("export_sidecars", END)
    return graph.compile()
