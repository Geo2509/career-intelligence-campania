from __future__ import annotations

from .config import load_yaml, match_keywords, signal_text


def detect_career(company: dict, config_path: str = "configs/business_keywords.yaml") -> dict:
    config = load_yaml(config_path)
    text = signal_text(company)
    career_matches = match_keywords(text, {"career_page": config.get("career_signals", {}).get("career_page", [])})
    hr_keywords = config.get("career_signals", {}).get("hr_email", [])
    emails = company.get("emails") or []
    hr_prefixes = [keyword.lower().rstrip("@") for keyword in hr_keywords]
    hr_email = next(
        (
            email
            for email in emails
            if any(email.lower().split("@", 1)[0] == prefix for prefix in hr_prefixes)
        ),
        "",
    )
    return {
        "career_page": company.get("career_url", "") if company.get("has_careers_page") else "",
        "career_email": hr_email,
        "hr_contact": hr_email,
        "hr_email": hr_email,
        "application_form": bool(company.get("contact_form") and company.get("has_careers_page")),
        "career_signals": sorted(career_matches),
    }
