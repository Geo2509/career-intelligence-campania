from __future__ import annotations

from pathlib import Path
import re

import yaml


def load_yaml(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def company_text(company: dict) -> str:
    values = []
    for key in (
        "company",
        "domain",
        "legal_name",
        "title",
        "snippet",
        "url",
        "website",
        "city",
        "region",
        "page_text",
        "contact_url",
        "career_url",
    ):
        values.append(str(company.get(key, "")))
    return " ".join(values).lower()


def signal_text(company: dict) -> str:
    values = []
    for key in (
        "domain",
        "legal_name",
        "website",
        "page_text",
        "contact_url",
        "career_url",
    ):
        values.append(str(company.get(key, "")))
    values.extend(str(email) for email in company.get("emails", []) or [])
    values.extend(str(phone) for phone in company.get("phones", []) or [])
    return " ".join(values).lower()


def phrase_in_text(text: str, phrase: str) -> bool:
    escaped = re.escape(phrase.lower().strip())
    if not escaped:
        return False
    return re.search(rf"(?<![\w]){escaped}(?![\w])", text.lower()) is not None


def match_keywords(text: str, grouped_keywords: dict[str, list[str]]) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {}
    for label, keywords in grouped_keywords.items():
        found = [keyword for keyword in keywords if phrase_in_text(text, keyword)]
        if found:
            matches[label] = found
    return matches
