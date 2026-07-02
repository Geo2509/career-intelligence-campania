from __future__ import annotations

from collections.abc import Iterable

from .base import SearchResult, normalize_url


class DuckDuckGoSearchClient:
    name = "duckduckgo"

    def search(self, query: str, max_results: int = 10) -> Iterable[SearchResult]:
        try:
            from ddgs import DDGS
        except ImportError:
            return []

        results: list[SearchResult] = []
        with DDGS() as ddgs:
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
                    )
                )
        return results
