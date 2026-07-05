from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


EVIDENCE_WEIGHTS: Dict[str, Dict[str, int]] = {
    # news/media
    "news": {
        "cronaca": 40,
        "giornale": 30,
        "redazione": 25,
        "articoli": 20,
        "notizie": 25,
        "news": 20,
        "magazine": 15,
    },
    # company signals
    "company": {
        "chi siamo": 40,
        "contatti": 25,
        "lavora con noi": 40,
        "careers": 30,
        "servizi": 35,
        "prodotti": 35,
        "clienti": 30,
        "azienda": 30,
        "societa": 25,
        "srl": 20,
        "spa": 20,
    },
    "government": {
        "amministrazione trasparente": 50,
        "albo pretorio": 40,
        "ministero": 40,
        "comune": 30,
        "municipio": 30,
        "gov.it": 50,
    },
    "education": {
        "universit": 40,
        "scuola": 30,
        "istituto": 30,
        "studenti": 20,
        "docenti": 20,
    },
    "directory": {
        "elenco aziende": 40,
        "pagine gialle": 40,
        "directory": 30,
        "scheda azienda": 25,
        "elenco": 15,
        "informazioni aziende": 30,
        "orari": 15,
    },
    "marketplace": {"marketplace": 40, "freelance": 25, "preventivi": 20, "professionisti": 15},
    "blog": {"blog": 30, "articolo": 20, "opinioni": 15},
    "association": {"associazione": 30, "associati": 20},
    "nonprofit": {"nonprofit": 35, "no profit": 35, "onlus": 30, "fondazione": 25},
    "healthcare": {"asl": 40, "ospedale": 30, "clinica": 25},
    "staffing_agency": {
        "randstad": 50,
        "adecco": 50,
        "manpower": 50,
        "grafton": 50,
        "page personnel": 50,
        "pagepersonnel": 50,
        "agenzia per il lavoro": 45,
        "somministrazione": 35,
        "staffing": 35,
        "recruitment": 35,
        "recruiting agency": 45,
        "temporary work": 35,
        "lavoro temporaneo": 35,
        "head hunting": 35,
        "selezione del personale": 40,
        "aziende clienti": 30,
    },
    "job_board": {
        "annunci": 30,
        "annunci lavoro": 40,
        "offerte di lavoro": 40,
        "cerca lavoro": 35,
        "pubblica annuncio": 40,
        "candidati ora": 30,
        "job alert": 30,
        "lavori disponibili": 35,
        "vacancy database": 40,
        "job": 20,
        "jobs": 20,
    },
}

NON_PROFILE_TYPES = {
    "job_board",
    "directory",
    "marketplace",
    "government",
    "municipality",
    "education",
    "university",
    "school",
    "media",
    "news",
    "blog",
    "association",
    "nonprofit",
    "healthcare",
}

POST_PROFILE_DOWNGRADE_TYPES = {
    "staffing_agency",
    "job_board",
    "directory",
    "marketplace",
    "public_service",
    "government",
    "municipality",
    "education",
    "university",
    "school",
    "media",
    "news",
    "blog",
    "association",
    "nonprofit",
    "non_employer",
}

POST_PROFILE_PRIORITY = [
    "staffing_agency",
    "job_board",
    "public_service",
    "directory",
    "marketplace",
    "government",
    "municipality",
    "education",
    "media",
    "news",
    "blog",
    "association",
    "nonprofit",
]

POST_PROFILE_EVIDENCE: Dict[str, Dict[str, int]] = {
    "staffing_agency": EVIDENCE_WEIGHTS["staffing_agency"],
    "job_board": EVIDENCE_WEIGHTS["job_board"],
    "directory": EVIDENCE_WEIGHTS["directory"],
    "marketplace": EVIDENCE_WEIGHTS["marketplace"],
    "public_service": {
        "servizi cittadino": 50,
        "servizi-cittadino": 50,
        "pratiche online": 35,
        "sportello": 30,
        "visure": 30,
        "comuni": 30,
        "amministrazioni": 30,
        "pubblica amministrazione": 35,
    },
    "government": EVIDENCE_WEIGHTS["government"],
    "municipality": {"comune": 35, "municipio": 35, "amministrazione comunale": 40},
    "education": EVIDENCE_WEIGHTS["education"],
    "media": EVIDENCE_WEIGHTS["news"],
    "news": EVIDENCE_WEIGHTS["news"],
    "blog": EVIDENCE_WEIGHTS["blog"],
    "association": EVIDENCE_WEIGHTS["association"],
    "nonprofit": EVIDENCE_WEIGHTS["nonprofit"],
}


def _text_candidates(company: Dict) -> str:
    parts = [
        company.get("company", ""),
        company.get("domain", ""),
        company.get("title", ""),
        company.get("snippet", ""),
        company.get("url", ""),
        company.get("website", ""),
        company.get("query", ""),
        company.get("original_query", ""),
        company.get("strategy", ""),
        company.get("discovery_strategy", ""),
        company.get("meta_description", ""),
        company.get("website_type", ""),
        company.get("contact_url", ""),
        company.get("career_url", ""),
        company.get("page_text", ""),
        company.get("industry", ""),
        company.get("phone", ""),
        company.get("qualification", ""),
        company.get("next_action", ""),
    ]
    parts.extend(_iter_values(company.get("emails")))
    parts.extend(_iter_values(company.get("phones")))
    parts.extend(_iter_values(company.get("business_type")))
    parts.extend(_iter_values(company.get("positive_reasons")))
    parts.extend(_iter_values(company.get("negative_reasons")))
    return " ".join(str(p).lower() for p in parts if p)


def _iter_values(values: object) -> Iterable[str]:
    if isinstance(values, list):
        return (str(value) for value in values if value)
    if values:
        return (str(values),)
    return ()


def classify_company(company: Dict) -> Tuple[str, int, List[str]]:
    """Classify a company-like record into a website type.

    Returns (website_type, confidence, reasons)
    """
    text = _text_candidates(company)
    domain = company.get("domain", "") or ""
    reasons: List[str] = []
    scores: Dict[str, int] = {}

    # evidence scoring from multiple buckets
    # domain-level hints
    if domain.endswith(".edu") or domain.endswith(".edu.it"):
        scores["education"] = scores.get("education", 0) + 40
        reasons.append("domain=.edu")
    if domain.endswith(".gov.it") or domain.endswith(".gov"):
        scores["government"] = scores.get("government", 0) + 50
        reasons.append("domain=.gov")
    if domain.endswith(".it") and domain.startswith("comune"):
        scores["municipality"] = scores.get("municipality", 0) + 40
        reasons.append("domain suggests municipality")

    # accumulate evidence from EVIDENCE_WEIGHTS across text
    for category, weight_map in EVIDENCE_WEIGHTS.items():
        for kw, weight in weight_map.items():
            if kw in text:
                scores[category] = scores.get(category, 0) + weight
                reasons.append(f"{kw}:{weight}")

    # if no evidence, return unknown
    if not scores:
        return "unknown", 0, []

    # determine best and second best for tie handling
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_cat, best_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    # tie handling
    if best_score - second_score < 15:
        return "unknown", 0, [f"tie:{best_score}-{second_score}"]

    # normalize confidence to 0-100 (cap)
    confidence = min(100, best_score)

    website_type = best_cat
    # map education nuance
    if website_type == "education":
        if "universit" in text:
            website_type = "university"
        elif "scuola" in text or "istituto" in text:
            website_type = "school"

    return website_type, confidence, reasons


def preserve_initial_website_type(company: Dict) -> Dict:
    """Store the pre-profile classification without changing compatibility fields."""
    preserved = dict(company)
    initial_type = preserved.get("website_type_initial", preserved.get("website_type", "unknown"))
    initial_confidence = preserved.get(
        "website_type_initial_confidence",
        preserved.get("website_type_confidence", preserved.get("website_type_score", 0)),
    )
    preserved["website_type_initial"] = initial_type or "unknown"
    preserved["website_type_initial_confidence"] = initial_confidence or 0
    preserved.setdefault("website_type_final", preserved.get("website_type", initial_type or "unknown"))
    preserved.setdefault("website_type_final_confidence", preserved.get("website_type_confidence", initial_confidence or 0))
    preserved.setdefault("website_type_final_reasons", preserved.get("website_type_reasons", []))
    return preserved


def post_profile_reclassify_company(company: Dict) -> Tuple[Dict, bool, bool]:
    """Reclassify after profiling/intelligence and downgrade obvious non-employers.

    Returns (updated_company, reclassified, send_cv_removed).
    """
    updated = preserve_initial_website_type(company)
    previous_type = str(updated.get("website_type", "") or "unknown")
    previous_action = updated.get("next_action", "")
    post_type, confidence, reasons = classify_post_profile_type(updated)

    if post_type:
        updated["website_type"] = post_type
        updated["website_type_confidence"] = confidence
        updated["website_type_score"] = confidence
        updated["website_type_reasons"] = reasons
        updated["website_type_final"] = post_type
        updated["website_type_final_confidence"] = confidence
        updated["website_type_final_reasons"] = reasons
    else:
        updated["website_type_final"] = updated.get("website_type", "unknown")
        updated["website_type_final_confidence"] = updated.get("website_type_confidence", 0)
        updated["website_type_final_reasons"] = updated.get("website_type_reasons", [])

    if updated.get("website_type") in POST_PROFILE_DOWNGRADE_TYPES:
        _apply_post_profile_downgrade(updated)

    reclassified = updated.get("website_type") != previous_type
    send_cv_removed = previous_action == "Send CV" and updated.get("next_action") != "Send CV"
    return updated, reclassified, send_cv_removed


def classify_post_profile_type(company: Dict) -> Tuple[str, int, List[str]]:
    text = _text_candidates(company)
    domain = str(company.get("domain", "") or "").lower()
    scores: Dict[str, int] = {}
    reasons: Dict[str, List[str]] = {}

    if domain.startswith("comune.") or domain.startswith("comune") or domain.endswith(".gov.it"):
        scores["government"] = scores.get("government", 0) + 50
        reasons.setdefault("government", []).append("domain suggests public sector:50")
    if "servizi-cittadino" in domain:
        scores["public_service"] = scores.get("public_service", 0) + 60
        reasons.setdefault("public_service", []).append("domain servizi-cittadino:60")

    for category, weight_map in POST_PROFILE_EVIDENCE.items():
        for keyword, weight in weight_map.items():
            if keyword in text:
                scores[category] = scores.get(category, 0) + weight
                reasons.setdefault(category, []).append(f"{keyword}:{weight}")

    if not scores:
        return "", 0, []

    best_type = max(POST_PROFILE_PRIORITY, key=lambda category: scores.get(category, 0))
    best_score = scores.get(best_type, 0)
    if best_score < 35:
        return "", 0, []

    if best_type == "education":
        if "universit" in text:
            best_type = "university"
        elif "scuola" in text or "istituto" in text:
            best_type = "school"

    return best_type, min(100, best_score), reasons.get(best_type, [])


def _apply_post_profile_downgrade(company: Dict) -> None:
    website_type = company.get("website_type", "")
    negative_reasons = list(company.get("negative_reasons", []))
    reason = f"Post-profile reclassified as {website_type}"
    if reason not in negative_reasons:
        negative_reasons.append(reason)
    company["negative_reasons"] = sorted(set(negative_reasons))

    if website_type == "staffing_agency":
        if company.get("qualification") in {"Excellent Match", "Good Match"}:
            company["qualification"] = "Possible Match"
        company["next_action"] = "Manual Review"
    elif website_type in POST_PROFILE_DOWNGRADE_TYPES:
        company["qualification"] = "Not Relevant"
        company["next_action"] = "Ignore"


def post_profile_reclassify_companies(companies: list[Dict]) -> tuple[list[Dict], dict[str, int]]:
    reclassified: list[Dict] = []
    stats = {
        "post_reclassified_count": 0,
        "post_reclassified_to_staffing_agency": 0,
        "post_reclassified_to_job_board": 0,
        "post_reclassified_to_directory": 0,
        "post_reclassified_to_public_sector": 0,
        "post_reclassified_to_media": 0,
        "post_reclassified_to_non_employer": 0,
        "send_cv_removed_by_reclassification": 0,
    }
    for company in companies:
        updated, changed, send_cv_removed = post_profile_reclassify_company(company)
        reclassified.append(updated)
        if changed:
            stats["post_reclassified_count"] += 1
            final_type = updated.get("website_type")
            if final_type == "staffing_agency":
                stats["post_reclassified_to_staffing_agency"] += 1
            elif final_type == "job_board":
                stats["post_reclassified_to_job_board"] += 1
            elif final_type == "directory":
                stats["post_reclassified_to_directory"] += 1
            elif final_type in {"public_service", "government", "municipality", "education", "university", "school"}:
                stats["post_reclassified_to_public_sector"] += 1
            elif final_type in {"media", "news", "blog"}:
                stats["post_reclassified_to_media"] += 1
            elif final_type in {"marketplace", "association", "nonprofit", "non_employer"}:
                stats["post_reclassified_to_non_employer"] += 1
        if send_cv_removed:
            stats["send_cv_removed_by_reclassification"] += 1
    return reclassified, stats
