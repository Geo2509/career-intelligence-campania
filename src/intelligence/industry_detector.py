from __future__ import annotations

from .config import load_yaml, match_keywords, signal_text


def detect_industry(company: dict, config_path: str = "configs/industry_keywords.yaml") -> dict:
    config = load_yaml(config_path)
    matches = match_keywords(signal_text(company), config.get("industries", {}))
    if not matches:
        return {"industry": "Unknown", "industry_matches": {}}
    industry = max(matches, key=lambda label: len(matches[label]))
    return {"industry": industry, "industry_matches": matches}
