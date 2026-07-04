from __future__ import annotations

from typing import Dict, List, Tuple


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
    },
    "marketplace": {"marketplace": 40, "freelance": 25, "preventivi": 20},
    "blog": {"blog": 30, "articolo": 20, "opinioni": 15},
    "association": {"associazione": 30},
    "healthcare": {"asl": 40, "ospedale": 30, "clinica": 25},
    "staffing_agency": {"randstad": 50, "adecco": 50, "manpower": 50, "agenzia per il lavoro": 40},
    "job_board": {"annunci": 30, "offerte di lavoro": 30, "job": 20, "jobs": 20},
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


def _text_candidates(company: Dict) -> str:
    parts = [
        company.get("domain", ""),
        company.get("title", ""),
        company.get("snippet", ""),
        company.get("url", ""),
        company.get("query", ""),
        company.get("original_query", ""),
        company.get("strategy", ""),
        company.get("discovery_strategy", ""),
        company.get("meta_description", ""),
    ]
    return " ".join(str(p).lower() for p in parts if p)


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
