from __future__ import annotations

from .config import load_yaml, match_keywords, signal_text


def detect_office(company: dict, config_path: str = "configs/business_keywords.yaml") -> dict:
    config = load_yaml(config_path)
    matches = match_keywords(signal_text(company), config.get("office_signals", {}))
    office_score = min(100, sum(len(values) for values in matches.values()) * 12)
    return {
        "office_signals": sorted(matches),
        "office_matches": matches,
        "office_score": office_score,
    }
