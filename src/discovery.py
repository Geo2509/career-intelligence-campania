from __future__ import annotations

from typing import Callable

from .query_generator import DiscoveryQuery, build_discovery_hash, generate_queries
from .search.search_manager import SearchRun, build_search_manager
from .discovery_optimization import rank_queries_for_execution


def discover_companies(
    search_engines_path: str = "configs/search_engines.yaml",
    limit_queries: int | None = None,
    engine: str = "duckduckgo",
) -> list[dict]:
    return [result.to_dict() for result in discover_search_results(search_engines_path, limit_queries, engine=engine).results]


def discover_search_results(
    search_engines_path: str = "configs/search_engines.yaml",
    limit_queries: int | None = None,
    engine: str = "duckduckgo",
    progress: Callable[[str], None] | None = None,
) -> SearchRun:
    all_queries, discovery_hash = generate_queries()
    ranked_queries = rank_queries_for_execution(all_queries)
    executed_queries = ranked_queries[:limit_queries] if limit_queries is not None else ranked_queries

    manager = build_search_manager(search_engines_path, discovery_hash, engine=engine)
    run = manager.run(executed_queries, progress=progress)
    return SearchRun(
        results=run.results,
        stats=run.stats,
        all_queries=all_queries,
        executed_queries=executed_queries,
        discovery_hash=discovery_hash,
    )
