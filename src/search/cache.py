from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .base import SearchResult, utc_now


CACHE_VERSION = 2


class SearchCache:
    def __init__(
        self,
        path: str | Path,
        ttl_hours: int = 168,
        enabled: bool = True,
        discovery_hash: str = "",
    ) -> None:
        self.path = Path(path)
        self.ttl = timedelta(hours=ttl_hours)
        self.enabled = enabled
        self.discovery_hash = discovery_hash
        self.discovery_version = CACHE_VERSION
        self._records = self._load()

    def _load(self) -> dict[str, list[dict]]:
        if not self.enabled or not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}

        version = data.get("discovery_version")
        hash_value = data.get("discovery_hash")
        if version != self.discovery_version or hash_value != self.discovery_hash:
            return {}

        records = data.get("records", {})
        if isinstance(records, dict):
            return {str(key): value for key, value in records.items() if isinstance(value, list)}
        return {}

    def _key(self, query: str, engine: str, strategy: str = "") -> str:
        return f"{engine}::{strategy}::{query}"

    def get(self, query: str, engine: str, strategy: str = "") -> list[SearchResult] | None:
        if not self.enabled:
            return None
        records = self._records.get(self._key(query, engine, strategy))
        if not records:
            return None
        if records[0].get("search_engine", records[0].get("engine", engine)) != engine:
            return None
        if records[0].get("strategy", "") != strategy:
            return None
        timestamp = records[0].get("timestamp", "")
        try:
            created_at = datetime.fromisoformat(timestamp)
        except ValueError:
            return None
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created_at > self.ttl:
            return None
        return [
            SearchResult(
                query=record.get("query", query),
                title=record.get("title", ""),
                url=record.get("url", ""),
                snippet=record.get("snippet", ""),
                source=record.get("search_engine", record.get("engine", engine)),
                strategy=record.get("strategy", ""),
                timestamp=record.get("timestamp", timestamp),
            )
            for record in records
        ]

    def set(self, query: str, engine: str, results: list[SearchResult], strategy: str = "") -> None:
        if not self.enabled:
            return
        timestamp = utc_now()
        self._records[self._key(query, engine, strategy)] = [
            {
                "query": result.query,
                "engine": engine,
                "search_engine": engine,
                "strategy": result.strategy,
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
                "timestamp": timestamp,
            }
            for result in results
        ]

    def save(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "discovery_version": self.discovery_version,
                    "discovery_hash": self.discovery_hash,
                    "records": self._records,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
