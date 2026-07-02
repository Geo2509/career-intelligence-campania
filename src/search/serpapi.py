from __future__ import annotations

import os
from collections.abc import Iterable

import requests

from .base import SearchResult, normalize_url


class SerpApiSearchClient:
    name = "serpapi"

    def __init__(self, api_key_env: str = "SERPAPI_API_KEY") -> None:
        self.api_key_env = api_key_env

    def search(self, query: str, max_results: int = 10) -> Iterable[SearchResult]:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            return []

        response = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "num": max_results,
                "gl": "it",
                "hl": "it",
            },
            timeout=20,
        )
        response.raise_for_status()

        results: list[SearchResult] = []
        for item in response.json().get("organic_results", [])[:max_results]:
            link = item.get("link", "")
            if not link:
                continue
            results.append(
                SearchResult(
                    query=query,
                    title=item.get("title", "").strip(),
                    url=normalize_url(link),
                    snippet=item.get("snippet", "").strip(),
                    source=self.name,
                )
            )
        return results
