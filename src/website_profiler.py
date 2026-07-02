from __future__ import annotations

import re
from dataclasses import dataclass, asdict

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
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def profile_website(url: str, timeout: int = 15) -> WebsiteProfile:
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "career-intelligence/0.1"})
        text = response.text[:200_000]
    except requests.RequestException as exc:
        return WebsiteProfile(url, None, [], [], False, False, str(exc))

    soup = BeautifulSoup(text, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    links = [link.get("href", "").lower() for link in soup.find_all("a")]
    lowered = page_text.lower()

    return WebsiteProfile(
        url=url,
        status_code=response.status_code,
        emails=sorted(set(EMAIL_RE.findall(page_text)))[:10],
        phones=sorted(set(PHONE_RE.findall(page_text)))[:10],
        has_contact_page=any("contatti" in href or "contact" in href for href in links)
        or "contatti" in lowered,
        has_careers_page=any("lavora-con-noi" in href or "careers" in href for href in links)
        or "lavora con noi" in lowered,
    )
