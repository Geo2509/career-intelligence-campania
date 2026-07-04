from __future__ import annotations

import os
import time
from collections.abc import Iterable

import requests

from .base import SearchResult, normalize_url, utc_now


class SerpApiSearchClient:
    name = "serpapi"

    def __init__(
        self,
        api_key_env: str = "SERPAPI_API_KEY",
        retries: int = 2,
        timeout: int = 20,
        rate_limit_seconds: float = 0.5,
    ) -> None:
        self.api_key_env = api_key_env
        self.retries = retries
        self.timeout = timeout
        self.rate_limit_seconds = rate_limit_seconds
        self.last_error = ""

    def search(self, query: str, max_results: int = 10) -> Iterable[SearchResult]:
        self.last_error = ""
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            self.last_error = f"missing API key env var: {self.api_key_env}"
            return []

        for attempt in range(self.retries + 1):
            try:
                response = requests.get(
                    "https://serpapi.com/search.json",
                    params={
                        "engine": "google",
                        "q": query,
                        "api_key": api_key,
                        # SerpAPI/Google defaults to about 10 organic results; SearchManager
                        # passes the configured limit here and we slice to the same ceiling below.
                        "num": max_results,
                        "gl": "it",
                        "hl": "it",
                    },
                    timeout=self.timeout,
                )
                if response.status_code in {402, 403, 429}:
                    self.last_error = f"quota/auth/rate limit status {response.status_code}"
                    return []
                response.raise_for_status()
                payload = response.json()
                error = payload.get("error")
                if error:
                    self.last_error = str(error)
                    return []

                results: list[SearchResult] = []
                for item in payload.get("organic_results", [])[:max_results]:
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
                            timestamp=utc_now(),
                        )
                    )
                time.sleep(self.rate_limit_seconds)
                return results
            except requests.RequestException as exc:
                self.last_error = str(exc)
                if attempt < self.retries:
                    time.sleep(self.rate_limit_seconds * (attempt + 1))
            except ValueError as exc:
                self.last_error = f"invalid JSON response: {exc}"
                return []
        return []
