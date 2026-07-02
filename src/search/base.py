from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "msclkid",
}


@dataclass(frozen=True)
class SearchResult:
    query: str
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    strategy: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        if not data["timestamp"]:
            data["timestamp"] = utc_now()
        return data

    def with_strategy(self, strategy: str) -> "SearchResult":
        return SearchResult(
            query=self.query,
            title=self.title,
            url=self.url,
            snippet=self.snippet,
            source=self.source,
            strategy=strategy,
            timestamp=self.timestamp,
        )


@dataclass
class SearchStats:
    queries_generated: int = 0
    queries_executed: int = 0
    cached_queries: int = 0
    live_queries: int = 0
    ddg_results: int = 0
    serpapi_results: int = 0
    search_errors: int = 0
    total_raw_results: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: list[str] = field(default_factory=list)
    queries_by_strategy: dict[str, int] = field(default_factory=dict)
    executed_queries_by_strategy: dict[str, int] = field(default_factory=dict)
    cache_hits_by_strategy: dict[str, int] = field(default_factory=dict)
    cache_misses_by_strategy: dict[str, int] = field(default_factory=dict)
    results_by_strategy: dict[str, int] = field(default_factory=dict)
    query_results: dict[str, int] = field(default_factory=dict)
    query_strategy_map: dict[str, str] = field(default_factory=dict)
    executed_query_texts: set[str] = field(default_factory=set)
    cached_query_texts: set[str] = field(default_factory=set)

    def record_results(self, engine: str, count: int) -> None:
        if engine == "duckduckgo":
            self.ddg_results += count
        elif engine == "serpapi":
            self.serpapi_results += count
        self.total_raw_results += count

    def record_error(self, engine: str, query: str, error: str) -> None:
        self.search_errors += 1
        self.errors.append(f"{engine}: {query}: {error}")

    def record_strategy_query(self, strategy: str, count: int = 1) -> None:
        self.queries_by_strategy[strategy] = self.queries_by_strategy.get(strategy, 0) + count

    def record_strategy_executed(self, strategy: str, count: int = 1) -> None:
        self.executed_queries_by_strategy[strategy] = self.executed_queries_by_strategy.get(strategy, 0) + count

    def record_cache_hit(self, strategy: str, count: int = 1) -> None:
        self.cache_hits += count
        self.cache_hits_by_strategy[strategy] = self.cache_hits_by_strategy.get(strategy, 0) + count

    def record_cache_miss(self, strategy: str, count: int = 1) -> None:
        self.cache_misses += count
        self.cache_misses_by_strategy[strategy] = self.cache_misses_by_strategy.get(strategy, 0) + count

    def record_cached_query(self, query: str) -> None:
        if query not in self.cached_query_texts:
            self.cached_query_texts.add(query)
            self.cached_queries += 1

    def record_live_query(self, query: str) -> None:
        if query not in self.executed_query_texts:
            self.executed_query_texts.add(query)
            self.live_queries += 1

    def record_strategy_result(self, strategy: str, count: int = 1) -> None:
        self.results_by_strategy[strategy] = self.results_by_strategy.get(strategy, 0) + count

    def mark_query_executed(self, query: str) -> None:
        self.executed_query_texts.add(query)

    def mark_query_cached(self, query: str) -> None:
        self.cached_query_texts.add(query)


class SearchClient(Protocol):
    name: str

    def search(self, query: str, max_results: int = 10) -> Iterable[SearchResult]:
        ...


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in TRACKING_PARAMS
        ]
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            query,
            "",
        )
    )
