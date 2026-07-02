from __future__ import annotations

from pathlib import Path

import yaml


def load_scoring_config(path: str | Path = "configs/scoring.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def score_company(company: dict, scoring_config: dict | None = None) -> dict:
    config = scoring_config or load_scoring_config()
    positive_weights = config.get("positive_weights", {})
    negative_weights = config.get("negative_weights", {})
    confidence_weights = config.get("confidence", {})
    score = 0
    positive_reasons: list[str] = list(company.get("positive_reasons", []))
    negative_reasons: list[str] = list(company.get("negative_reasons", []))
    text = " ".join(str(company.get(key, "")) for key in ("domain", "page_text", "category")).lower()

    for keyword, weight in positive_weights.items():
        if keyword.lower() in text and keyword not in positive_reasons:
            score += int(weight)
            positive_reasons.append(keyword)
    for keyword, weight in negative_weights.items():
        if keyword.lower() in text and keyword not in negative_reasons:
            score += int(weight)
            negative_reasons.append(keyword)

    if company.get("emails") and "email" not in positive_reasons and "Email found" not in positive_reasons:
        score += int(positive_weights.get("email", 20))
        positive_reasons.append("Email found")
    if company.get("has_careers_page") and "career page" not in positive_reasons and "Careers page" not in positive_reasons:
        score += int(positive_weights.get("career page", 12))
        positive_reasons.append("Careers page")

    confidence = 0
    if company.get("is_employer"):
        confidence += int(confidence_weights.get("validated_employer", 25))
    if company.get("emails"):
        confidence += int(confidence_weights.get("email_found", 25))
    if company.get("phones"):
        confidence += int(confidence_weights.get("phone_found", 15))
    if company.get("has_contact_page"):
        confidence += int(confidence_weights.get("contact_page", 15))
    if company.get("has_careers_page"):
        confidence += int(confidence_weights.get("career_page", 10))
    if company.get("linkedin"):
        confidence += int(confidence_weights.get("linkedin", 5))
    if company.get("facebook"):
        confidence += int(confidence_weights.get("facebook", 5))

    scored = dict(company)
    scored["score"] = max(0, score + int(company.get("qualification_score", 0)))
    scored["confidence"] = min(100, confidence)
    scored["positive_reasons"] = sorted(set(positive_reasons))
    scored["negative_reasons"] = sorted(set(negative_reasons))
    scored["score_reasons"] = ",".join(positive_reasons)
    scored["why_relevant"] = "; ".join(scored["positive_reasons"])
    scored["next_action"] = company.get("next_action") or (
        "Email direct contact" if company.get("emails") else "Check contact/careers page"
    )
    return scored


def score_companies(companies: list[dict], scoring_path: str | Path = "configs/scoring.yaml") -> list[dict]:
    config = load_scoring_config(scoring_path)
    return sorted(
        (score_company(company, config) for company in companies),
        key=lambda item: (item["score"], item["confidence"]),
        reverse=True,
    )
