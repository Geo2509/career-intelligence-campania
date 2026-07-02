from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+39\s?)?(?:0\d{1,3}[\s.-]?)?\d{6,10}")


@dataclass
class WebsiteProfile:
    url: str
    status_code: int | None
    emails: list[str]
    phones: list[str]
    has_contact_page: bool
    has_careers_page: bool
    contact_url: str = ""
    career_url: str = ""
    contact_form: bool = False
    linkedin: str = ""
    facebook: str = ""
    page_text: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _same_domain(base_url: str, candidate_url: str) -> bool:
    return urlparse(base_url).netloc.lower().removeprefix("www.") == urlparse(candidate_url).netloc.lower().removeprefix("www.")


def _interesting_internal_links(base_url: str, soup: BeautifulSoup) -> list[str]:
    links: list[str] = []
    for link in soup.find_all("a"):
        href = link.get("href", "")
        label = link.get_text(" ", strip=True).lower()
        absolute = urljoin(base_url, href)
        lowered = f"{href} {label}".lower()
        if not _same_domain(base_url, absolute):
            continue
        if any(word in lowered for word in ("contatti", "contact", "lavora", "careers", "chi-siamo", "about")):
            if absolute not in links:
                links.append(absolute)
    return links[:3]


def _fetch(url: str, timeout: int) -> tuple[int | None, str, str]:
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "career-intelligence/0.1"})
        return response.status_code, response.text[:200_000], ""
    except requests.RequestException as exc:
        return None, "", str(exc)


def profile_website(url: str, timeout: int = 15, max_internal_pages: int = 3) -> WebsiteProfile:
    status_code, text, error = _fetch(url, timeout)
    if error:
        return WebsiteProfile(url, status_code, [], [], False, False, error=error)

    soup = BeautifulSoup(text, "html.parser")
    pages = [(url, soup)]
    for link in _interesting_internal_links(url, soup)[:max_internal_pages]:
        link_status, link_text, link_error = _fetch(link, timeout)
        if link_error or link_status is None:
            continue
        pages.append((link, BeautifulSoup(link_text, "html.parser")))

    all_text_parts: list[str] = []
    all_links: list[tuple[str, str]] = []
    has_form = False
    for page_url, page_soup in pages:
        all_text_parts.append(page_soup.get_text(" ", strip=True))
        has_form = has_form or bool(page_soup.find("form"))
        for link in page_soup.find_all("a"):
            href = link.get("href", "")
            all_links.append((urljoin(page_url, href), link.get_text(" ", strip=True).lower()))

    page_text = " ".join(all_text_parts)
    lowered = page_text.lower()
    contact_url = ""
    career_url = ""
    linkedin = ""
    facebook = ""
    for href, label in all_links:
        link_text = f"{href} {label}".lower()
        if not contact_url and any(word in link_text for word in ("contatti", "contact")):
            contact_url = href
        if not career_url and any(word in link_text for word in ("lavora", "careers")):
            career_url = href
        if not linkedin and "linkedin.com" in href:
            linkedin = href
        if not facebook and "facebook.com" in href:
            facebook = href

    return WebsiteProfile(
        url=url,
        status_code=status_code,
        emails=sorted(set(EMAIL_RE.findall(page_text)))[:10],
        phones=sorted(set(PHONE_RE.findall(page_text)))[:10],
        has_contact_page=bool(contact_url) or "contatti" in lowered or "contact" in lowered,
        has_careers_page=bool(career_url) or "lavora con noi" in lowered or "careers" in lowered,
        contact_url=contact_url,
        career_url=career_url,
        contact_form=has_form,
        linkedin=linkedin,
        facebook=facebook,
        page_text=page_text[:5000],
    )
