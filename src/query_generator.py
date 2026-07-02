from __future__ import annotations

from pathlib import Path

import yaml


def _load_yaml(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def generate_queries(
    roles_path: str | Path = "configs/roles.yaml",
    locations_path: str | Path = "configs/locations.yaml",
    intents_path: str | Path = "configs/search_intents.yaml",
) -> list[str]:
    roles = _load_yaml(roles_path).get("roles", [])
    locations = _load_yaml(locations_path).get("locations", [])
    intents = _load_yaml(intents_path).get("intents", {})

    queries: list[str] = []
    seen: set[str] = set()
    for intent in intents.values():
        for template in intent.get("templates", []):
            for role in roles:
                for location in locations:
                    query = template.format(role=role, location=location).strip()
                    if query and query not in seen:
                        seen.add(query)
                        queries.append(query)
    return queries
