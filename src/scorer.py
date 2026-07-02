from __future__ import annotations


def score_company(company: dict) -> dict:
    score = 0
    reasons: list[str] = []
    text = " ".join(
        str(company.get(key, "")) for key in ("company", "domain", "title", "snippet", "url")
    ).lower()

    if any(word in text for word in ("data", "back office", "amministr", "ai", "customer")):
        score += 25
        reasons.append("role_match")
    if any(place.lower() in text for place in ("napoli", "pozzuoli", "bacoli", "campania")):
        score += 20
        reasons.append("location_match")
    if company.get("emails"):
        score += 25
        reasons.append("direct_email")
    if company.get("has_contact_page"):
        score += 15
        reasons.append("contact_page")
    if company.get("has_careers_page"):
        score += 15
        reasons.append("careers_page")

    scored = dict(company)
    scored["score"] = score
    scored["score_reasons"] = ",".join(reasons)
    return scored


def score_companies(companies: list[dict]) -> list[dict]:
    return sorted((score_company(company) for company in companies), key=lambda item: item["score"], reverse=True)
