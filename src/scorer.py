from __future__ import annotations

from pathlib import Path
from typing import Iterable

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
    priority = employer_priority(scored)
    scored.update(priority)
    scored["next_action"] = next_action_for_priority(scored["employer_priority_score"])
    return scored


def score_companies(companies: list[dict], scoring_path: str | Path = "configs/scoring.yaml") -> list[dict]:
    config = load_scoring_config(scoring_path)
    return sorted(
        (score_company(company, config) for company in companies),
        key=lambda item: (item["employer_priority_score"], item["score"], item["confidence"]),
        reverse=True,
    )


def employer_priority(company: dict) -> dict:
    score = 30
    reasons: list[str] = []
    positive_count = 0
    negative_count = 0
    text = _company_text(company)
    website_type = str(company.get("website_type_final") or company.get("website_type") or "").lower()
    industry = str(company.get("industry", "")).lower()
    business_types = {str(value).lower() for value in _values(company.get("business_type"))}
    office_signals = {str(value).lower() for value in _values(company.get("office_signals"))}

    def add(points: int, reason: str) -> None:
        nonlocal score, positive_count
        score += points
        positive_count += 1
        reasons.append(f"+{points} {reason}")

    def subtract(points: int, reason: str) -> None:
        nonlocal score, negative_count
        score -= points
        negative_count += 1
        reasons.append(f"-{points} {reason}")

    if company.get("is_employer") or website_type == "company":
        add(14, "direct employer")
    else:
        subtract(12, "no direct employer evidence")

    if company.get("has_careers_page") or company.get("career_page") or company.get("career_url"):
        add(10, "career page")
    else:
        subtract(8, "no career page")

    if company.get("hr_email"):
        add(10, "HR email")
    if company.get("has_contact_page") or company.get("contact_url"):
        add(6, "contact page")
    if company.get("emails"):
        add(8, "company email")
    else:
        subtract(8, "no company email")

    if industry in {"logistics", "shipping", "freight forwarding", "import export", "manufacturing"}:
        add(12, f"{company.get('industry')} company")
    if any(term in text for term in ("warehouse", "magazzino", "deposito")):
        add(8, "warehouse company")
    if "back office" in office_signals or "back office" in text:
        add(8, "back office company")
    if any(term in text for term in ("document management", "gestione documentale", "archiviazione", "document processing")):
        add(8, "document management")
    if any(term in text for term in ("data entry", "inserimento dati")):
        add(8, "data entry services")
    if "b2b" in business_types or "b2b" in text:
        add(6, "B2B company")
    if str(company.get("company_size", "")).lower() in {"medium", "large"}:
        add(6, "medium/large company")

    location_text = " ".join(
        str(company.get(key, "")).lower() for key in ("city", "region", "domain", "page_text", "snippet", "title")
    )
    if "campania" in location_text:
        add(8, "Campania")
    for place in ("napoli", "pozzuoli", "bacoli", "monte di procida"):
        if place in location_text:
            add(8, place.title())
            break
    if any(term in text for term in ("sede", "filiale", "ufficio", "local office", "local offices")):
        add(5, "local offices")
    if any(term in text for term in ("lavora con noi", "posizioni aperte", "careers", "offerte di lavoro")):
        add(10, "active recruitment indicators")

    target_terms = (
        "data entry",
        "back office",
        "administration",
        "amministrazione",
        "import/export",
        "import export",
        "logistics",
        "logistica",
        "supply chain",
        "document processing",
        "operations",
        "customer operations",
        "office support",
    )
    target_hits = [term for term in target_terms if term in text]
    if target_hits:
        add(min(18, 6 + len(target_hits) * 4), "target profile match")

    if any(reason == "Weak geographic fit" for reason in (company.get("negative_reasons") or [])):
        subtract(15, "weak geographic fit")
    if industry == "it" and not any(term in text for term in ("logistica", "logistics", "data entry", "back office")):
        subtract(12, "generic IT company")
    if any(term in text for term in ("marketing agency", "agenzia marketing", "web marketing", "social media agency")):
        subtract(20, "marketing agency")
    if "consulting only" in text or ("consulting" in text and not target_hits):
        subtract(15, "consulting only")
    if "retail only" in text or industry == "retail":
        subtract(18, "retail only")
    if any(term in text for term in ("personal website", "portfolio personale", "freelancer", "libero professionista")):
        subtract(25, "personal/freelancer site")

    type_penalties = {
        "education": 30,
        "university": 30,
        "school": 30,
        "association": 30,
        "municipality": 35,
        "government": 35,
        "public_service": 35,
        "media": 30,
        "news": 30,
        "blog": 30,
        "marketplace": 35,
        "directory": 40,
        "job_board": 50,
        "staffing_agency": 55,
        "nonprofit": 30,
        "non_employer": 50,
    }
    if website_type in type_penalties:
        subtract(type_penalties[website_type], website_type.replace("_", " "))

    priority_score = max(0, min(100, score))
    confidence = max(
        0,
        min(
            100,
            35 + positive_count * 7 + negative_count * 5 + int(company.get("confidence", 0) or 0) // 4,
        ),
    )
    return {
        "employer_priority_score": priority_score,
        "employer_priority_reasons": reasons,
        "employer_priority_confidence": confidence,
    }


def next_action_for_priority(priority_score: int) -> str:
    if priority_score >= 80:
        return "Send CV"
    if priority_score >= 60:
        return "Manual Review"
    if priority_score >= 40:
        return "Monitor Careers"
    return "Ignore"


def _company_text(company: dict) -> str:
    fields = (
        "company",
        "domain",
        "title",
        "snippet",
        "query",
        "original_query",
        "discovery_strategy",
        "page_text",
        "category",
        "industry",
        "city",
        "region",
        "qualification",
        "website_type",
        "website_type_final",
    )
    parts = [str(company.get(field, "")) for field in fields]
    for field in ("business_type", "positive_reasons", "negative_reasons", "office_signals", "logistics_signals"):
        parts.extend(_values(company.get(field)))
    return " ".join(part.lower() for part in parts if part)


def _values(values: object) -> Iterable[str]:
    if isinstance(values, list):
        return [str(value) for value in values if value]
    if values:
        return [str(values)]
    return []
