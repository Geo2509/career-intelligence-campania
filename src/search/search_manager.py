from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml

from .base import SearchClient, SearchResult
from .duckduckgo import DuckDuckGoSearchClient
from .serpapi import SerpApiSearchClient


def load_search_clients(config_path: str | Path) -> list[tuple[SearchClient, int]]:
    config = yaml.safe_load(Path(config_path).read_text()) or {}
    engines = config.get("engines", {})
    clients: list[tuple[SearchClient, int]] = []

    duckduckgo = engines.get("duckduckgo", {})
    if duckduckgo.get("enabled", False):
        clients.append((DuckDuckGoSearchClient(), int(duckduckgo.get("max_results", 10))))

    serpapi = engines.get("serpapi", {})
    if serpapi.get("enabled", False):
        clients.append(
            (
                SerpApiSearchClient(serpapi.get("api_key_env", "SERPAPI_API_KEY")),
                int(serpapi.get("max_results", 10)),
            )
        )

    return clients


class SearchManager:
    def __init__(self, clients: list[tuple[SearchClient, int]]) -> None:
        self.clients = clients

    def search_many(self, queries: Iterable[str]) -> list[SearchResult]:
        results: list[SearchResult] = []
        for query in queries:
            for client, max_results in self.clients:
                results.extend(client.search(query, max_results=max_results))
        return results
