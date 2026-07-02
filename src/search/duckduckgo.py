from __future__ import annotations

from collections.abc import Iterable
import time

from .base import SearchResult, normalize_url, utc_now


class DuckDuckGoSearchClient:
    name = "duckduckgo"

    def __init__(self, retries: int = 2, timeout: int = 20, rate_limit_seconds: float = 1.0) -> None:
        self.retries = retries
        self.timeout = timeout
        self.rate_limit_seconds = rate_limit_seconds
        self.last_error = ""

    def search(self, query: str, max_results: int = 10) -> Iterable[SearchResult]:
        self.last_error = ""
        try:
            from ddgs import DDGS
        except ImportError as exc:
            self.last_error = str(exc)
            return []

        for attempt in range(self.retries + 1):
            try:
                results: list[SearchResult] = []
                with DDGS(timeout=self.timeout) as ddgs:
                    for item in ddgs.text(query, max_results=max_results):
                        href = item.get("href") or item.get("url") or ""
                        if not href:
                            continue
                        results.append(
                            SearchResult(
                                query=query,
                                title=item.get("title", "").strip(),
                                url=normalize_url(href),
                                snippet=item.get("body", "").strip(),
                                source=self.name,
                                timestamp=utc_now(),
                            )
                        )
                time.sleep(self.rate_limit_seconds)
                return results
            except Exception as exc:
                self.last_error = str(exc)
                if attempt < self.retries:
                    time.sleep(self.rate_limit_seconds * (attempt + 1))
        return []
