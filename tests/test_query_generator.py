from pathlib import Path

from src.query_generator import generate_queries


def test_generate_queries_from_templates(tmp_path: Path) -> None:
    roles = tmp_path / "roles.yaml"
    locations = tmp_path / "locations.yaml"
    intents = tmp_path / "intents.yaml"

    roles.write_text("roles:\n  - data entry\n")
    locations.write_text("locations:\n  - Napoli\n")
    intents.write_text("intents:\n  direct:\n    templates:\n      - '{role} {location} contatti'\n")

    assert generate_queries(roles, locations, intents) == ["data entry Napoli contatti"]
