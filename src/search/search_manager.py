from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Callable

import yaml

from .base import SearchClient, SearchResult, SearchStats
from .cache import SearchCache
from .duckduckgo import DuckDuckGoSearchClient
from ..query_generator import DiscoveryQuery
from .serpapi import SerpApiSearchClient


@dataclass
class SearchRun:
    results: list[SearchResult]
    stats: SearchStats
    all_queries: list[DiscoveryQuery] = field(default_factory=list)
    executed_queries: list[DiscoveryQuery] = field(default_factory=list)
    discovery_hash: str = ""


def load_search_config(config_path: str | Path) -> dict:
    return yaml.safe_load(Path(config_path).read_text()) or {}


def load_search_clients(config_path: str | Path, engine: str = "duckduckgo") -> list[tuple[SearchClient, int]]:
    load_environment()
    config = load_search_config(config_path)
    engines = config.get("engines", {})
    clients: list[tuple[SearchClient, int]] = []
    requested = _selected_engines(engine)

    duckduckgo = engines.get("duckduckgo", {})
    if "duckduckgo" in requested and duckduckgo.get("enabled", True):
        clients.append(
            (
                DuckDuckGoSearchClient(
                    retries=int(duckduckgo.get("retries", 2)),
                    timeout=int(duckduckgo.get("timeout", 20)),
                    rate_limit_seconds=float(duckduckgo.get("rate_limit_seconds", 1.0)),
                ),
                _configured_limit(duckduckgo),
            )
        )

    serpapi = engines.get("serpapi", {})
    serpapi_key_env = serpapi.get("api_key_env", "SERPAPI_API_KEY")
    serpapi_available = bool(os.getenv(serpapi_key_env))
    if "serpapi" in requested and serpapi_available:
        clients.append(
            (
                SerpApiSearchClient(
                    serpapi_key_env,
                    retries=int(serpapi.get("retries", 2)),
                    timeout=int(serpapi.get("timeout", 20)),
                    rate_limit_seconds=float(serpapi.get("rate_limit_seconds", 0.5)),
                ),
                _configured_limit(serpapi),
            )
        )
    elif "serpapi" in requested and not serpapi_available:
        print(
            f"Warning: {serpapi_key_env} is not set; SerpAPI is unavailable. Falling back to DuckDuckGo.",
            file=sys.stderr,
        )
        duckduckgo = engines.get("duckduckgo", {})
        if not clients and duckduckgo.get("enabled", True):
            clients.append(
                (
                    DuckDuckGoSearchClient(
                        retries=int(duckduckgo.get("retries", 2)),
                        timeout=int(duckduckgo.get("timeout", 20)),
                        rate_limit_seconds=float(duckduckgo.get("rate_limit_seconds", 1.0)),
                    ),
                    _configured_limit(duckduckgo),
                )
            )

    return clients


class SearchManager:
    def __init__(self, clients: list[tuple[SearchClient, int]], cache: SearchCache | None = None) -> None:
        self.clients = clients
        self.cache = cache

    def search_many(self, queries: Iterable[str]) -> list[SearchResult]:
        return self.run(queries).results

    def run(self, queries: Iterable[str], progress: Callable[[str], None] | None = None) -> SearchRun:
        query_list = list(queries)
        stats = SearchStats(queries_generated=len(query_list))
        results: list[SearchResult] = []

        if progress:
            progress(f"Generated queries: {len(query_list)}")

        for index, query_item in enumerate(query_list, start=1):
            query_text = getattr(query_item, "query", str(query_item))
            strategy = getattr(query_item, "strategy", "")
            stats.record_strategy_query(strategy)

            if progress:
                progress("")
                progress(f"[{index}/{len(query_list)}] {query_text}")
            for client, max_results in self.clients:
                stats.record_engine_query(client.name)
                stats.query_results.setdefault(query_text, 0)
                stats.query_strategy_map[query_text] = strategy
                cached = self.cache.get(query_text, client.name, strategy=strategy) if self.cache else None
                if cached is not None:
                    stats.record_cache_hit(strategy)
                    stats.record_strategy_executed(strategy)
                    stats.record_cached_query(query_text)
                    stats.record_results(client.name, len(cached))
                    stats.record_strategy_result(strategy, len(cached))
                    stats.query_results[query_text] += len(cached)
                    cached = [result.with_strategy(strategy) if strategy else result for result in cached]
                    results.extend(cached)
                    if progress:
                        progress(f"  {engine_label(client.name)}: {len(cached)} results (cache)")
                    continue

                stats.record_cache_miss(strategy)
                stats.record_live_query(query_text)
                stats.queries_executed += 1
                stats.record_strategy_executed(strategy)
                try:
                    engine_results = list(client.search(query_text, max_results=max_results))
                except Exception as exc:
                    stats.record_error(client.name, query_text, str(exc))
                    continue

                engine_results = [result.with_strategy(strategy) for result in engine_results]
                last_error = getattr(client, "last_error", "")
                if last_error and not engine_results:
                    stats.record_error(client.name, query_text, last_error)
                    if progress:
                        progress(f"  {engine_label(client.name)}: 0 results ({last_error})")
                elif progress:
                    progress(f"  {engine_label(client.name)}: {len(engine_results)} results")

                stats.record_results(client.name, len(engine_results))
                stats.record_strategy_result(strategy, len(engine_results))
                results.extend(engine_results)
                if self.cache is not None:
                    self.cache.set(query_text, client.name, engine_results, strategy=strategy)

        if self.cache is not None:
            self.cache.save()
        return SearchRun(results=results, stats=stats)


def build_search_manager(config_path: str | Path, discovery_hash: str, engine: str = "duckduckgo") -> SearchManager:
    config = load_search_config(config_path)
    cache_config = config.get("cache", {})
    cache = SearchCache(
        cache_config.get("path", "output/cache/search_results.json"),
        ttl_hours=int(cache_config.get("ttl_hours", 168)),
        enabled=bool(cache_config.get("enabled", True)),
        discovery_hash=discovery_hash,
    )
    return SearchManager(load_search_clients(config_path, engine=engine), cache=cache)


def engine_label(name: str) -> str:
    labels = {
        "duckduckgo": "DDG",
        "serpapi": "SerpAPI",
    }
    return labels.get(name, name)


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        env_path = Path(".env")
        if not env_path.exists():
            return
        for raw_line in env_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
        return
    load_dotenv(dotenv_path=Path(".env"))


def _configured_limit(engine_config: dict) -> int:
    return int(engine_config.get("limit", engine_config.get("max_results", 10)))


def _selected_engines(engine: str) -> set[str]:
    if engine == "all":
        return {"duckduckgo", "serpapi"}
    if engine in {"duckduckgo", "serpapi"}:
        return {engine}
    raise ValueError(f"Unknown search engine: {engine}")
