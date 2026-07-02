from __future__ import annotations

from src.company_extractor import load_excluded_domain_classes, excluded_domain_type

from .config import load_yaml, phrase_in_text


QUALIFICATION_RANK = {
    "Not Relevant": 0,
    "Low Match": 1,
    "Possible Match": 2,
    "Good Match": 3,
    "Excellent Match": 4,
}


def cap_qualification(current: str, cap: str) -> str:
    return current if QUALIFICATION_RANK[current] <= QUALIFICATION_RANK[cap] else cap


def qualify_company(company: dict, config_path: str = "configs/qualification.yaml") -> dict:
    config = load_yaml(config_path)
    weights = config.get("weights", {})
    score = 0
    positive: list[str] = []
    negative: list[str] = []

    industry = company.get("industry", "Unknown")
    score += int(weights.get("industry", {}).get(industry, 0))
    if industry in {"Logistics", "Shipping", "Freight Forwarding", "Import Export"}:
        positive.append("Logistics company")
    elif industry == "Retail":
        negative.append("Retail only")

    for business_type in company.get("business_type", []):
        score += int(weights.get("business_type", {}).get(business_type, 0))

    if company.get("logistics_score", 0) > 0:
        score += min(25, int(company["logistics_score"]) // 2)
    if company.get("office_score", 0) > 0:
        score += min(20, int(company["office_score"]) // 2)
    if company.get("career_page"):
        positive.append("Careers page")
    if company.get("general_email"):
        positive.append("Email found")
    if company.get("hr_email"):
        positive.append("HR email found")
    if "Documentation" in company.get("logistics_signals", []):
        positive.append("Documentation")
    if "Import" in company.get("logistics_signals", []) or "Export" in company.get("logistics_signals", []):
        positive.append("Import Export")
    if "Back Office" in company.get("office_signals", []):
        positive.append("Back Office")
    if any(signal in company.get("office_signals", []) for signal in ("Excel", "ERP", "SAP", "Office 365")):
        positive.append("Office tools")
    if company.get("region") in {"Campania", "Puglia", "Calabria"}:
        positive.append(company["region"])

    text = " ".join(str(company.get(key, "")) for key in ("title", "snippet", "page_text")).lower()
    for reason, keywords in config.get("negative_signals", {}).items():
        if any(phrase_in_text(text, keyword) for keyword in keywords) and reason not in negative:
            negative.append(reason)
    if not company.get("general_email") and not company.get("career_page") and not company.get("contact_url"):
        negative.append("No contact path")
    if not direct_employer_evidence(company):
        negative.append("No direct employer evidence")

    for reason in positive:
        score += int(weights.get("positive_reason_weights", {}).get(reason, 0))
    for reason in negative:
        score += int(weights.get("negative_reason_weights", {}).get(reason, 0))

    thresholds = config.get("qualification", {})
    if score >= int(thresholds.get("excellent_min_score", 70)):
        qualification = "Excellent Match"
    elif score >= int(thresholds.get("good_min_score", 45)):
        qualification = "Good Match"
    elif score >= int(thresholds.get("possible_min_score", 25)):
        qualification = "Possible Match"
    elif score >= int(thresholds.get("low_min_score", 10)):
        qualification = "Low Match"
    else:
        qualification = "Not Relevant"

    excluded_type = excluded_domain_type(company.get("domain", ""), load_excluded_domain_classes())
    if excluded_type:
        reason = f"Excluded domain: {excluded_type}"
        if reason not in negative:
            negative.append(reason)
        if excluded_type == "staffing_agency":
            qualification = cap_qualification(qualification, "Possible Match")
        else:
            qualification = "Not Relevant"

    if not company.get("general_email") and not company.get("contact_url") and not company.get("career_page"):
        qualification = cap_qualification(qualification, "Low Match")
    if not company.get("career_page"):
        qualification = cap_qualification(qualification, "Good Match")
    if not direct_employer_evidence(company):
        qualification = cap_qualification(qualification, "Possible Match")
    if industry == "Retail" or phrase_in_text(text, "retail only"):
        qualification = cap_qualification(qualification, "Possible Match")
    if web_agency_only(company):
        if "Web agency / marketing only" not in negative:
            negative.append("Web agency / marketing only")
        qualification = cap_qualification(qualification, "Possible Match")

    next_action = config.get("next_actions", {}).get(qualification, "Manual Review")
    if excluded_type == "staffing_agency":
        next_action = "Manual Review"
    elif excluded_type:
        next_action = "Ignore"
    return {
        "qualification_score": max(0, score),
        "qualification": qualification,
        "positive_reasons": sorted(set(company.get("positive_reasons", []) + positive)),
        "negative_reasons": sorted(set(company.get("negative_reasons", []) + negative)),
        "next_action": next_action,
    }


def direct_employer_evidence(company: dict) -> bool:
    if company.get("is_employer") and (
        company.get("general_email") or company.get("contact_url") or company.get("career_page")
    ):
        return True
    if company.get("career_page") and company.get("domain") in str(company.get("career_page")):
        return True
    if company.get("general_email") and company.get("domain", "").split(".")[0] in company.get("general_email", ""):
        return True
    return False


def web_agency_only(company: dict) -> bool:
    text = " ".join(str(company.get(key, "")) for key in ("page_text", "title", "snippet")).lower()
    web_terms = ("web agency", "digital marketing", "seo", "social media", "copywriting", "e-commerce")
    logistics_terms = ("logistica", "spedizioni", "import export", "dogana", "supply chain")
    return any(phrase_in_text(text, term) for term in web_terms) and not any(
        phrase_in_text(text, term) for term in logistics_terms
    )
