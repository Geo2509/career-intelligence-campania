from __future__ import annotations

from .company_extractor import domain_from_url
from .search.base import normalize_url


def dedupe_companies(companies: list[dict]) -> list[dict]:
    seen_domains: set[str] = set()
    seen_urls: set[str] = set()
    unique: list[dict] = []

    for company in companies:
        url = normalize_url(company.get("url", ""))
        domain = company.get("domain") or domain_from_url(url)
        if domain in seen_domains or url in seen_urls:
            continue
        seen_domains.add(domain)
        seen_urls.add(url)
        normalized = dict(company)
        normalized["url"] = url
        normalized["domain"] = domain
        unique.append(normalized)
    return unique
