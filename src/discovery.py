from __future__ import annotations

from .query_generator import generate_queries
from .search.search_manager import SearchManager, load_search_clients


def discover_companies(
    search_engines_path: str = "configs/search_engines.yaml",
    limit_queries: int | None = None,
) -> list[dict]:
    queries = generate_queries()
    if limit_queries is not None:
        queries = queries[:limit_queries]

    manager = SearchManager(load_search_clients(search_engines_path))
    return [result.to_dict() for result in manager.search_many(queries)]
