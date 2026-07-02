from __future__ import annotations

import re
from urllib.parse import urlparse


JOB_BOARD_HINTS = {"indeed", "jooble", "talent", "infojobs", "jobrapido", "subito"}


def domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def company_name_from_title(title: str, domain: str) -> str:
    cleaned = re.split(r"[\-|:|–|—]", title, maxsplit=1)[0].strip()
    if cleaned and len(cleaned) <= 80:
        return cleaned
    return domain.split(".")[0].replace("-", " ").title()


def extract_companies(results: list[dict], negative_keywords: list[str] | None = None) -> list[dict]:
    negatives = [keyword.lower() for keyword in (negative_keywords or [])]
    companies: list[dict] = []

    for item in results:
        url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        haystack = f"{url} {title} {snippet}".lower()
        domain = domain_from_url(url)

        if not domain or any(hint in domain for hint in JOB_BOARD_HINTS):
            continue
        if any(keyword in haystack for keyword in negatives):
            continue

        companies.append(
            {
                "company": company_name_from_title(title, domain),
                "domain": domain,
                "url": url,
                "title": title,
                "snippet": snippet,
                "query": item.get("query", ""),
                "source": item.get("source", ""),
            }
        )
    return companies
