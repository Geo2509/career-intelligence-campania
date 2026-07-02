from __future__ import annotations

from .company_extractor import domain_from_url
from .search.base import normalize_url


def dedupe_companies(companies: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    by_domain: dict[str, dict] = {}
    unique: list[dict] = []

    for company in companies:
        url = normalize_url(company.get("url", ""))
        domain = company.get("domain") or domain_from_url(url)
        if url in seen_urls and domain in by_domain:
            continue
        seen_urls.add(url)
        if domain in by_domain:
            existing = by_domain[domain]
            queries = existing.get("queries", []) + company.get("queries", [])
            engines = existing.get("engines", []) + company.get("engines", [])
            if queries:
                existing["queries"] = sorted(set(queries))
            if engines:
                existing["engines"] = sorted(set(engines))
            if len(company.get("snippet", "")) > len(existing.get("snippet", "")):
                existing["snippet"] = company.get("snippet", "")
                existing["title"] = company.get("title", existing.get("title", ""))
                existing["url"] = url
            continue
        normalized = dict(company)
        normalized["url"] = url
        normalized["domain"] = domain
        if normalized.get("queries"):
            normalized["queries"] = sorted(set(normalized.get("queries", [])))
        if normalized.get("engines"):
            normalized["engines"] = sorted(set(normalized.get("engines", [])))
        by_domain[domain] = normalized
        unique.append(normalized)
    return unique
