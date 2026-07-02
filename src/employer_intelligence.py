from __future__ import annotations

from .intelligence.business_detector import detect_business
from .intelligence.career_detector import detect_career
from .intelligence.contact_detector import detect_contacts
from .intelligence.industry_detector import detect_industry
from .intelligence.logistics_detector import detect_logistics
from .intelligence.office_detector import detect_office
from .intelligence.qualification import qualify_company


def enrich_company(company: dict) -> dict:
    enriched = dict(company)
    enriched.setdefault("legal_name", company.get("company", ""))
    enriched.setdefault("country", "Italy" if enriched.get("domain", "").endswith(".it") else "")
    enriched.update(detect_industry(enriched))
    enriched.update(detect_business(enriched))
    enriched.update(detect_logistics(enriched))
    enriched.update(detect_office(enriched))
    enriched.update(detect_career(enriched))
    enriched.update(detect_contacts(enriched))
    enriched.update(qualify_company(enriched))
    enriched["category"] = enriched.get("industry", enriched.get("category", ""))
    return enriched


def enrich_companies(companies: list[dict]) -> list[dict]:
    return [enrich_company(company) for company in companies]
