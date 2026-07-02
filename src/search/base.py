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
    timestamp: str = ""

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        if not data["timestamp"]:
            data["timestamp"] = utc_now()
        return data


@dataclass
class SearchStats:
    queries_generated: int = 0
    queries_executed: int = 0
    ddg_results: int = 0
    serpapi_results: int = 0
    search_errors: int = 0
    total_raw_results: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: list[str] = field(default_factory=list)

    def record_results(self, engine: str, count: int) -> None:
        if engine == "duckduckgo":
            self.ddg_results += count
        elif engine == "serpapi":
            self.serpapi_results += count
        self.total_raw_results += count

    def record_error(self, engine: str, query: str, error: str) -> None:
        self.search_errors += 1
        self.errors.append(f"{engine}: {query}: {error}")


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
