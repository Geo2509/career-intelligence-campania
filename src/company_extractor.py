from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

DEFAULT_AGGREGATORS = {
    "indeed",
    "linkedin.com/jobs",
    "jooble",
    "talent.com",
    "monster",
    "careerjet",
    "subito",
    "infojobs",
    "glassdoor",
    "simplyhired",
    "jobillico",
    "recruit.net",
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
    return (yaml.safe_load(config_path.read_text()) or {}).get("aggregators", sorted(DEFAULT_AGGREGATORS))


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

        companies.append(
            {
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
                "source": item.get("source", ""),
                "queries": [item.get("query", "")] if item.get("query") else [],
                "engines": [item.get("source", "")] if item.get("source") else [],
            }
        )
    return companies
