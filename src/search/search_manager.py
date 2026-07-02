from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from .base import SearchClient, SearchResult, SearchStats
from .cache import SearchCache
from .duckduckgo import DuckDuckGoSearchClient
from .serpapi import SerpApiSearchClient


@dataclass
class SearchRun:
    results: list[SearchResult]
    stats: SearchStats


def load_search_config(config_path: str | Path) -> dict:
    return yaml.safe_load(Path(config_path).read_text()) or {}


def load_search_clients(config_path: str | Path) -> list[tuple[SearchClient, int]]:
    config = load_search_config(config_path)
    engines = config.get("engines", {})
    clients: list[tuple[SearchClient, int]] = []

    duckduckgo = engines.get("duckduckgo", {})
    if duckduckgo.get("enabled", False):
        clients.append(
            (
                DuckDuckGoSearchClient(
                    retries=int(duckduckgo.get("retries", 2)),
                    timeout=int(duckduckgo.get("timeout", 20)),
                    rate_limit_seconds=float(duckduckgo.get("rate_limit_seconds", 1.0)),
                ),
                int(duckduckgo.get("max_results", 10)),
            )
        )

    serpapi = engines.get("serpapi", {})
    if serpapi.get("enabled", False):
        clients.append(
            (
                SerpApiSearchClient(
                    serpapi.get("api_key_env", "SERPAPI_API_KEY"),
                    retries=int(serpapi.get("retries", 2)),
                    timeout=int(serpapi.get("timeout", 20)),
                    rate_limit_seconds=float(serpapi.get("rate_limit_seconds", 0.5)),
                ),
                int(serpapi.get("max_results", 10)),
            )
        )

    return clients


class SearchManager:
    def __init__(self, clients: list[tuple[SearchClient, int]], cache: SearchCache | None = None) -> None:
        self.clients = clients
        self.cache = cache

    def search_many(self, queries: Iterable[str]) -> list[SearchResult]:
        return self.run(queries).results

    def run(self, queries: Iterable[str]) -> SearchRun:
        query_list = list(queries)
        stats = SearchStats(queries_generated=len(query_list))
        results: list[SearchResult] = []

        for query in query_list:
            for client, max_results in self.clients:
                cached = self.cache.get(query, client.name) if self.cache else None
                if cached is not None:
                    stats.cache_hits += 1
                    stats.record_results(client.name, len(cached))
                    results.extend(cached)
                    continue

                stats.cache_misses += 1
                stats.queries_executed += 1
                try:
                    engine_results = list(client.search(query, max_results=max_results))
                except Exception as exc:
                    stats.record_error(client.name, query, str(exc))
                    continue

                last_error = getattr(client, "last_error", "")
                if last_error and not engine_results:
                    stats.record_error(client.name, query, last_error)

                stats.record_results(client.name, len(engine_results))
                results.extend(engine_results)
                if self.cache is not None:
                    self.cache.set(query, client.name, engine_results)

        if self.cache is not None:
            self.cache.save()
        return SearchRun(results=results, stats=stats)


def build_search_manager(config_path: str | Path) -> SearchManager:
    config = load_search_config(config_path)
    cache_config = config.get("cache", {})
    cache = SearchCache(
        cache_config.get("path", "output/cache/search_results.json"),
        ttl_hours=int(cache_config.get("ttl_hours", 168)),
        enabled=bool(cache_config.get("enabled", True)),
    )
    return SearchManager(load_search_clients(config_path), cache=cache)
