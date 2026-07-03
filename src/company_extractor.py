from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

DEFAULT_AGGREGATORS = {
    "indeed.com",
    "indeed.it",
    "linkedin.com",
    "jooble.org",
    "jooble.com",
    "talent.com",
    "monster.it",
    "careerjet.it",
    "subito.it",
    "infojobs.it",
    "glassdoor.it",
    "simplyhired.com",
    "jobillico.com",
    "recruit.net",
    "jobijoba.it",
    "jobsora.com",
    "randstad.it",
    "gigroup.it",
    "addlance.com",
    "europages.it",
    "prontopro.it",
}

LOCATION_HINTS = {
    "napoli": ("Napoli", "Campania"),
    "pozzuoli": ("Pozzuoli", "Campania"),
    "bacoli": ("Bacoli", "Campania"),
    "monte di procida": ("Monte di Procida", "Campania"),
    "campania": ("", "Campania"),
    "puglia": ("", "Puglia"),
    "calabria": ("", "Calabria"),
}


def domain_from_url(url: str) -> str:
    return root_domain(urlparse(url).netloc.lower())


def root_domain(hostname: str) -> str:
    hostname = hostname.split(":")[0].strip(".").removeprefix("www.")
    parts = [part for part in hostname.split(".") if part]
    if len(parts) <= 2:
        return ".".join(parts)
    return ".".join(parts[-2:])


def load_aggregators(path: str | Path = "configs/aggregators.yaml") -> list[str]:
    config_path = Path(path)
    if not config_path.exists():
        return sorted(DEFAULT_AGGREGATORS)
    config = yaml.safe_load(config_path.read_text()) or {}
    if "aggregators" in config:
        return config.get("aggregators", sorted(DEFAULT_AGGREGATORS))
    excluded = config.get("excluded_domains", {})
    domains: list[str] = []
    for values in excluded.values():
        domains.extend(values or [])
    return sorted(set(domains))


def load_excluded_domain_classes(path: str | Path = "configs/aggregators.yaml") -> dict[str, str]:
    config_path = Path(path)
    if not config_path.exists():
        return {domain: "intermediary" for domain in DEFAULT_AGGREGATORS}
    config = yaml.safe_load(config_path.read_text()) or {}
    excluded = config.get("excluded_domains", {})
    classes: dict[str, str] = {}
    for category, domains in excluded.items():
        for domain in domains or []:
            classes[domain.lower()] = category
    for domain in config.get("aggregators", []):
        classes.setdefault(domain.lower(), "intermediary")
    return classes


def company_name_from_title(title: str, domain: str) -> str:
    cleaned = re.split(r"[\-|:|–|—]", title, maxsplit=1)[0].strip()
    if cleaned and len(cleaned) <= 80:
        return cleaned
    return domain.split(".")[0].replace("-", " ").title()


def infer_location(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for hint, location in LOCATION_HINTS.items():
        if hint in lowered:
            return location
    return "", ""


def is_aggregator(url: str, aggregators: list[str]) -> bool:
    lowered = url.lower()
    return any(aggregator.lower() in lowered for aggregator in aggregators)


def excluded_domain_type(domain: str, excluded_classes: dict[str, str]) -> str:
    lowered = domain.lower()
    for excluded_domain, category in excluded_classes.items():
        if lowered == excluded_domain or lowered.endswith(f".{excluded_domain}"):
            return category
    return ""


def _calculate_discovery_confidence(company: dict) -> int:
    text = " ".join(
        str(company.get(key, "")) for key in ("title", "snippet", "query", "strategy")
    ).lower()
    score = 20
    if "site:.it" in company.get("query", ""):
        score += 20
    if any(term in text for term in ("azienda", "società", "societa", "srl", "spa", "società", "impresa", "azienda")):
        score += 15
    if any(term in text for term in ("contatti", "chi siamo", "lavora con noi", "posizioni aperte", "careers", "career", "join us")):
        score += 20
    if any(term in text for term in ("servizi", "service provider", "soluzioni", "borsa lavoro")):
        score += 5
    if any(term in text for term in ("offerte di lavoro", "annunci", "job board", "portale", "directory", "elenco aziende", "pagina gialla", "bacheca", "jobs", "indeed", "jooble", "prontopro", "subito", "jobijoba", "jobbydoo", "europages", "linkedin", "infojobs", "careerjet", "monster", "jobrapido")):
        score -= 35
    if any(term in text for term in ("servizi", "consulenza", "soluzioni", "service provider")) and "azienda" not in text:
        score -= 10
    if "lavoro" in company.get("query", "") and "contatti" not in company.get("query", "") and "lavora con noi" not in company.get("query", ""):
        score -= 10
    if company.get("strategy") == "company_website_search":
        score += 20
    if company.get("strategy") == "career_search":
        score += 10
    if company.get("strategy") == "business_search":
        score -= 5
    if company.get("strategy") == "service_search":
        score -= 10
    if company.get("strategy") == "logistics_search" and "data entry" in company.get("query", ""):
        score -= 10
    return max(0, min(100, score))


def _map_discovery_confidence_level(confidence: int) -> str:
    if confidence >= 80:
        return "High"
    if confidence >= 60:
        return "Medium"
    if confidence >= 40:
        return "Low"
    return "Ignore"


def extract_companies(
    results: list[dict],
    negative_keywords: list[str] | None = None,
    aggregators: list[str] | None = None,
) -> list[dict]:
    negatives = [keyword.lower() for keyword in (negative_keywords or [])]
    aggregator_hints = aggregators or load_aggregators()
    companies: list[dict] = []

    for item in results:
        url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        haystack = f"{url} {title} {snippet}".lower()
        domain = domain_from_url(url)

        if not domain or is_aggregator(url, aggregator_hints):
            continue
        if any(keyword in haystack for keyword in negatives):
            continue
        city, region = infer_location(f"{title} {snippet} {url} {item.get('query', '')}")

        source = item.get("source", "") or item.get("engine", "")
        strategy = item.get("strategy", "") or item.get("query_strategy", "")
        company = {
            "company": company_name_from_title(title, domain),
            "domain": domain,
            "city": city,
            "region": region,
            "category": "",
            "url": url,
            "website": f"https://{domain}",
            "title": title,
            "snippet": snippet,
            "query": item.get("query", ""),
            "original_query": item.get("query", ""),
            "source": source,
            "search_engine": source,
            "strategy": strategy,
            "discovery_strategy": strategy,
            "queries": [item.get("query", "")] if item.get("query") else [],
            "engines": [source] if source else [],
            "strategies": [strategy] if strategy else [],
        }
        company["discovery_confidence"] = _calculate_discovery_confidence(company)
        company["discovery_confidence_level"] = _map_discovery_confidence_level(company["discovery_confidence"])
        companies.append(company)
    return companies
