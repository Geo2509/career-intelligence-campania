from __future__ import annotations

from typing import Callable

from .query_generator import generate_queries
from .search.search_manager import SearchRun, build_search_manager


def discover_companies(
    search_engines_path: str = "configs/search_engines.yaml",
    limit_queries: int | None = None,
) -> list[dict]:
    return [result.to_dict() for result in discover_search_results(search_engines_path, limit_queries).results]


def discover_search_results(
    search_engines_path: str = "configs/search_engines.yaml",
    limit_queries: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> SearchRun:
    queries = generate_queries()
    if limit_queries is not None:
        queries = queries[:limit_queries]

    manager = build_search_manager(search_engines_path)
    return manager.run(queries, progress=progress)
