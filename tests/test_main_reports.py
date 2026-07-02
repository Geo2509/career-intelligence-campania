import json
from pathlib import Path

from src.main import run
from src.query_generator import generate_queries


def test_run_metadata_written(tmp_path: Path, monkeypatch):
    output_base = tmp_path / "campania_targets"
    history_path = tmp_path / "history.json"
    search_config = tmp_path / "search_engines.yaml"

    search_config.write_text(
        "engines:\n"
        "  duckduckgo:\n"
        "    enabled: false\n"
        "cache:\n"
        "  enabled: false\n"
    )
    (tmp_path / "configs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs" / "roles.yaml").write_text("roles:\n  - data entry\n")
    (tmp_path / "configs" / "locations.yaml").write_text("locations:\n  - Napoli\n")
    (tmp_path / "configs" / "negative_keywords.yaml").write_text("negative_keywords:\n  - none\n")
    (tmp_path / "configs" / "scoring.yaml").write_text(
        "positive_weights:\n"
        "  email: 20\n"
        "  career page: 12\n"
        "confidence:\n"
        "  validated_employer: 25\n"
        "  email_found: 25\n"
        "  phone_found: 15\n"
        "  contact_page: 15\n"
        "  career_page: 10\n"
        "  linkedin: 5\n"
        "  facebook: 5\n"
    )
    (tmp_path / "configs" / "discovery.yaml").write_text(
        "strategies:\n"
        "  direct:\n"
        "    enabled: true\n"
        "    priority: 10\n"
        "    templates:\n"
        "      - '{role} {location} contatti'\n"
    )

    monkeypatch.chdir(tmp_path)
    records, stats = run(
        limit_queries=0,
        profile=False,
        output_base=str(output_base),
        search_engines_path=str(search_config),
        history_path=str(history_path),
        verbose=False,
    )

    metadata_path = Path("output/run_metadata.json")
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text())
    assert metadata["generated_queries"] == 1
    assert metadata["executed_queries"] == 0
    assert metadata["cache_hits"] == 0
    assert metadata["cache_misses"] == 0
    assert metadata["raw_results"] == 0
    assert metadata["unique_companies"] == 0


def test_discovery_health_written(tmp_path: Path, monkeypatch):
    output_base = tmp_path / "campania_targets"
    history_path = tmp_path / "history.json"
    search_config = tmp_path / "search_engines.yaml"

    search_config.write_text(
        "engines:\n"
        "  duckduckgo:\n"
        "    enabled: false\n"
        "cache:\n"
        "  enabled: false\n"
    )
    (tmp_path / "configs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs" / "roles.yaml").write_text("roles:\n  - data entry\n")
    (tmp_path / "configs" / "locations.yaml").write_text("locations:\n  - Napoli\n")
    (tmp_path / "configs" / "negative_keywords.yaml").write_text("negative_keywords:\n  - none\n")
    (tmp_path / "configs" / "scoring.yaml").write_text(
        "positive_weights:\n"
        "  email: 20\n"
        "  career page: 12\n"
        "confidence:\n"
        "  validated_employer: 25\n"
        "  email_found: 25\n"
        "  phone_found: 15\n"
        "  contact_page: 15\n"
        "  career_page: 10\n"
        "  linkedin: 5\n"
        "  facebook: 5\n"
    )
    (tmp_path / "configs" / "discovery.yaml").write_text(
        "strategies:\n"
        "  direct:\n"
        "    enabled: true\n"
        "    priority: 10\n"
        "    templates:\n"
        "      - '{role} {location} contatti'\n"
    )

    monkeypatch.chdir(tmp_path)
    run(
        limit_queries=0,
        profile=False,
        output_base=str(output_base),
        search_engines_path=str(search_config),
        history_path=str(history_path),
        verbose=False,
    )

    health_path = Path("output/discovery_health.json")
    assert health_path.exists()
    health = json.loads(health_path.read_text())
    assert "strategies_configured" in health
    assert "queries_with_zero_results" in health
    assert isinstance(health["queries_never_executed"], list)
