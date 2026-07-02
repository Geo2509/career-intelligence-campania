from __future__ import annotations

from .config import load_yaml, match_keywords, signal_text


def detect_business(company: dict, config_path: str = "configs/business_keywords.yaml") -> dict:
    config = load_yaml(config_path)
    text = signal_text(company)
    business_matches = match_keywords(text, config.get("business_types", {}))
    business_types = sorted(business_matches)
    size_matches = match_keywords(text, config.get("size_signals", {}))
    company_size = "Unknown"
    for size in ("Enterprise", "Large", "Medium", "Small"):
        if size in size_matches:
            company_size = size
            break
    return {
        "business_type": business_types,
        "business_matches": business_matches,
        "company_size": company_size,
        "company_size_matches": size_matches,
    }
