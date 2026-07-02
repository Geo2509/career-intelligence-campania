from pathlib import Path

from src.query_generator import DiscoveryQuery, generate_queries


def test_generate_queries_from_templates(tmp_path: Path) -> None:
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


def test_generate_queries_uses_strategy_and_deduplicates(tmp_path: Path) -> None:
    roles = tmp_path / "roles.yaml"
    locations = tmp_path / "locations.yaml"
    discovery = tmp_path / "discovery.yaml"

    roles.write_text("roles:\n  - data entry\n")
    locations.write_text("locations:\n  - Napoli\n")
    discovery.write_text(
        "strategies:\n"
        "  a:\n"
        "    enabled: true\n"
        "    priority: 20\n"
        "    templates:\n"
        "      - '{role} {location} contatti'\n"
        "  b:\n"
        "    enabled: true\n"
        "    priority: 10\n"
        "    templates:\n"
        "      - '{role} {location} contatti'\n"
    )

    queries, discovery_hash = generate_queries(roles, locations, discovery)
    assert len(queries) == 1
    assert queries[0].strategy == "a"
    assert isinstance(discovery_hash, str)
    assert len(discovery_hash) == 64
