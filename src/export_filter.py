from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .company_extractor import root_domain


EXPORT_FILTER_REPORT_PATH = Path("output/export_filter_report.json")

BLACKLIST_DOMAINS = {
    "facebook.com": "social_media",
    "instagram.com": "social_media",
    "youtube.com": "video_platform",
    "youtu.be": "video_platform",
    "tiktok.com": "social_media",
    "x.com": "social_media",
    "twitter.com": "social_media",
    "tripadvisor.com": "travel_portal",
    "tripadvisor.it": "travel_portal",
    "travorium.com": "travel_portal",
    "similarweb.com": "generic_platform",
    "clutch.co": "directory_only",
    "google.com": "search_engine",
    "bing.com": "search_engine",
    "wikipedia.org": "wiki",
    "reddit.com": "forum",
}

NEVER_EXPORT_TYPES = {
    "social_media",
    "video_platform",
    "forum",
    "wiki",
    "search_engine",
    "directory_only",
    "review_site",
    "travel_portal",
    "browser_vendor",
    "analytics",
    "ad_network",
    "generic_platform",
    "non_employer",
}

TYPE_CATEGORY = {
    "social_media": "social_media",
    "video_platform": "platforms",
    "forum": "platforms",
    "wiki": "platforms",
    "search_engine": "platforms",
    "directory_only": "non_employers",
    "review_site": "reviews",
    "travel_portal": "travel",
    "browser_vendor": "platforms",
    "analytics": "platforms",
    "ad_network": "platforms",
    "generic_platform": "platforms",
    "non_employer": "non_employers",
}

KEYWORD_TYPES = {
    "youtube": "video_platform",
    "facebook": "social_media",
    "instagram": "social_media",
    "tiktok": "social_media",
    "twitter": "social_media",
    "tripadvisor": "travel_portal",
    "travorium": "travel_portal",
    "wikipedia": "wiki",
    "reddit": "forum",
    "similarweb": "generic_platform",
    "clutch": "directory_only",
    "google maps": "search_engine",
    "maps.google": "search_engine",
}

REPORT_KEYS = {
    "removed_by_export_filter": 0,
    "removed_social_media": 0,
    "removed_reviews": 0,
    "removed_travel": 0,
    "removed_platforms": 0,
    "removed_non_employers": 0,
    "removed_blacklist": 0,
}


def apply_final_export_filter(companies: list[dict]) -> tuple[list[dict], dict]:
    kept: list[dict] = []
    removed: list[dict] = []
    counts = dict(REPORT_KEYS)

    for company in companies:
        decision = export_filter_decision(company)
        if not decision["remove"]:
            kept.append(company)
            continue

        removed.append(
            {
                "domain": company_domain(company),
                "url": company.get("url", ""),
                "company": company.get("company", ""),
                "removal_reason": decision["reason"],
                "category": decision["category"],
                "website_type": company.get("website_type_final") or company.get("website_type", ""),
            }
        )
        counts["removed_by_export_filter"] += 1
        counts[f"removed_{decision['category']}"] += 1
        if decision["blacklist"]:
            counts["removed_blacklist"] += 1

    report = {
        **counts,
        "counts_per_category": {
            "social_media": counts["removed_social_media"],
            "reviews": counts["removed_reviews"],
            "travel": counts["removed_travel"],
            "platforms": counts["removed_platforms"],
            "non_employers": counts["removed_non_employers"],
            "blacklist": counts["removed_blacklist"],
        },
        "removed_domains": removed,
    }
    return kept, report


def export_filter_decision(company: dict) -> dict:
    domain = company_domain(company)
    host = company_host(company)
    website_type = str(company.get("website_type_final") or company.get("website_type") or "").lower()
    inferred_type = BLACKLIST_DOMAINS.get(domain) or inferred_platform_type(company, domain, host)

    if inferred_type:
        if linkedin_career_exception(company, domain):
            return keep_decision()
        return remove_decision(
            reason=f"blacklisted {inferred_type}: {domain}",
            category=category_for_type(inferred_type),
            blacklist=True,
        )

    if website_type in NEVER_EXPORT_TYPES and not direct_employer_exception(company):
        return remove_decision(
            reason=f"excluded website type: {website_type}",
            category=category_for_type(website_type),
            blacklist=False,
        )

    return keep_decision()


def write_export_filter_report(report: dict, path: str | Path = EXPORT_FILTER_REPORT_PATH) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def company_domain(company: dict) -> str:
    domain = str(company.get("domain", "") or "").lower().removeprefix("www.")
    if domain:
        return root_domain(domain)
    return root_domain(company_host(company))


def company_host(company: dict) -> str:
    for field in ("url", "website"):
        value = str(company.get(field, "") or "")
        if not value:
            continue
        parsed = urlparse(value if "://" in value else f"https://{value}")
        if parsed.netloc:
            return parsed.netloc.lower().removeprefix("www.")
    return ""


def inferred_platform_type(company: dict, domain: str, host: str) -> str:
    text = " ".join(
        str(company.get(field, ""))
        for field in ("domain", "url", "website", "title", "snippet", "website_type", "website_type_final")
    ).lower()
    if host.startswith("maps.google.") or "maps.google." in text:
        return "search_engine"
    for keyword, platform_type in KEYWORD_TYPES.items():
        if keyword in domain or keyword in host or keyword in text:
            return platform_type
    return ""


def direct_employer_exception(company: dict) -> bool:
    return bool(
        company.get("is_employer")
        or company.get("hr_email")
        or company.get("career_url")
        or company.get("career_page")
        or company.get("has_careers_page")
        or (company.get("emails") and company.get("has_contact_page"))
    )


def linkedin_career_exception(company: dict, domain: str) -> bool:
    if domain != "linkedin.com":
        return False
    text = " ".join(str(company.get(field, "")) for field in ("url", "career_url", "title", "snippet")).lower()
    return bool(company.get("is_employer") and ("career" in text or "jobs" in text))


def category_for_type(platform_type: str) -> str:
    return TYPE_CATEGORY.get(platform_type, "platforms")


def keep_decision() -> dict:
    return {"remove": False, "reason": "", "category": "", "blacklist": False}


def remove_decision(reason: str, category: str, blacklist: bool) -> dict:
    return {"remove": True, "reason": reason, "category": category, "blacklist": blacklist}
