from __future__ import annotations


POSITIVE_SIGNALS = {
    "lavora con noi",
    "careers",
    "contatti",
    "contact",
    "chi siamo",
    "partita iva",
    "azienda",
    "servizi",
}

NEGATIVE_SIGNALS = {
    "directory",
    "blog",
    "forum",
    "news",
    "job board",
    "offerte lavoro",
    "annunci lavoro",
    "recruiting agency",
}


def validate_employer(company: dict) -> dict:
    text = " ".join(
        str(company.get(key, ""))
        for key in (
            "company",
            "domain",
            "title",
            "snippet",
            "url",
            "page_text",
            "contact_url",
            "career_url",
        )
    ).lower()
    positive = sorted(signal for signal in POSITIVE_SIGNALS if signal in text)
    negative = sorted(signal for signal in NEGATIVE_SIGNALS if signal in text)
    is_employer = bool(positive) and not negative
    if company.get("emails") or company.get("has_contact_page") or company.get("has_careers_page"):
        is_employer = not negative

    validated = dict(company)
    validated["is_employer"] = is_employer
    validated["validation_positive"] = positive
    validated["validation_negative"] = negative
    return validated


def filter_valid_employers(companies: list[dict], allow_unconfirmed: bool = True) -> list[dict]:
    validated = [validate_employer(company) for company in companies]
    if allow_unconfirmed:
        return [company for company in validated if not company["validation_negative"]]
    return [company for company in validated if company["is_employer"]]
