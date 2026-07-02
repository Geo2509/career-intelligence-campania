from pathlib import Path

import pytest

from src.company_extractor import _map_discovery_confidence_level
from src.main import audit_cache
from src.query_generator import DiscoveryQuery, generate_queries


def test_discovery_confidence_level_mapping() -> None:
    assert _map_discovery_confidence_level(100) == "High"
    assert _map_discovery_confidence_level(80) == "High"
    assert _map_discovery_confidence_level(79) == "Medium"
    assert _map_discovery_confidence_level(60) == "Medium"
    assert _map_discovery_confidence_level(59) == "Low"
    assert _map_discovery_confidence_level(40) == "Low"
    assert _map_discovery_confidence_level(39) == "Ignore"
    assert _map_discovery_confidence_level(0) == "Ignore"


def test_generate_queries_and_discovery_hash(tmp_path: Path) -> None:
    roles = tmp_path / "roles.yaml"
    locations = tmp_path / "locations.yaml"
    discovery = tmp_path / "discovery.yaml"

    roles.write_text("roles:\n  - data entry\n")
    locations.write_text("locations:\n  - Napoli\n")
    discovery.write_text(
        "strategies:\n"
        "  direct:\n"
        "    enabled: true\n"
        "    priority: 10\n"
        "    templates:\n"
        "      - '{role} {location} contatti'\n"
    )

    queries, discovery_hash = generate_queries(roles, locations, discovery)
    assert queries == [DiscoveryQuery(query="data entry Napoli contatti", strategy="direct")]
    assert isinstance(discovery_hash, str)
    assert len(discovery_hash) == 64


def test_cache_audit_reports_obsolete_entry(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "output" / "cache" / "search_results.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        '{\n'
        '  "discovery_version": 0,\n'
        '  "discovery_hash": "oldhash",\n'
        '  "records": {"duckduckgo::test query": []}\n'
        '}'
    )

    (tmp_path / "configs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs" / "search_engines.yaml").write_text(
        "engines:\n"
        "  duckduckgo:\n"
        "    enabled: false\n"
        "cache:\n"
        "  enabled: false\n"
    )
    (tmp_path / "configs" / "roles.yaml").write_text("roles:\n  - data entry\n")
    (tmp_path / "configs" / "locations.yaml").write_text("locations:\n  - Napoli\n")
    (tmp_path / "configs" / "negative_keywords.yaml").write_text("negative_keywords:\n  - none\n")
    (tmp_path / "configs" / "discovery.yaml").write_text(
        "strategies:\n"
        "  direct:\n"
        "    enabled: true\n"
        "    priority: 10\n"
        "    templates:\n"
        "      - '{role} {location} contatti'\n"
    )

    monkeypatch.chdir(tmp_path)
    audit = audit_cache("configs/search_engines.yaml")

    assert audit["cache_entries"] == 1
    assert audit["obsolete_cache_entries"] == 1
    assert audit["current_discovery_hash"] != "oldhash"
    assert audit["queries_not_matching_current_discovery"] == ["test query"]
