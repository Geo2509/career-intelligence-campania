from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DiscoveryQuery:
    query: str
    strategy: str


def _load_yaml(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text()) or {}


def build_discovery_hash(discovery_path: str | Path = "configs/discovery.yaml") -> str:
    content = Path(discovery_path).read_text()
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate_queries(
    roles_path: str | Path = "configs/roles.yaml",
    locations_path: str | Path = "configs/locations.yaml",
    discovery_path: str | Path = "configs/discovery.yaml",
) -> tuple[list[DiscoveryQuery], str]:
    roles = _load_yaml(roles_path).get("roles", [])
    locations = _load_yaml(locations_path).get("locations", [])
    discovery = _load_yaml(discovery_path).get("strategies", {})
    discovery_hash = build_discovery_hash(discovery_path)

    queries: list[DiscoveryQuery] = []
    seen: set[str] = set()
    for strategy_name, strategy in sorted(
        discovery.items(),
        key=lambda item: int(item[1].get("priority", 0)),
        reverse=True,
    ):
        if not strategy.get("enabled", True):
            continue
        templates = strategy.get("templates", [])
        limit = int(strategy["limit"]) if strategy.get("limit") is not None else None
        added = 0

        for template in templates:
            for role in roles:
                for location in locations:
                    query = template.format(role=role, location=location).strip()
                    if not query or query in seen:
                        continue
                    seen.add(query)
                    queries.append(DiscoveryQuery(query=query, strategy=strategy_name))
                    added += 1
                    if limit is not None and added >= limit:
                        break
                if limit is not None and added >= limit:
                    break
            if limit is not None and added >= limit:
                break

    return queries, discovery_hash
