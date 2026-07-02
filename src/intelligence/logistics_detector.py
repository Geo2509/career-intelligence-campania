from __future__ import annotations

from .config import load_yaml, match_keywords, signal_text


def detect_logistics(company: dict, config_path: str = "configs/business_keywords.yaml") -> dict:
    config = load_yaml(config_path)
    matches = match_keywords(signal_text(company), config.get("logistics_signals", {}))
    logistics_score = min(100, sum(len(values) for values in matches.values()) * 10)
    return {
        "logistics_signals": sorted(matches),
        "logistics_matches": matches,
        "logistics_score": logistics_score,
    }
