from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "msclkid",
}


@dataclass(frozen=True)
class SearchResult:
    query: str
    title: str
    url: str
    snippet: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class SearchClient(Protocol):
    name: str

    def search(self, query: str, max_results: int = 10) -> Iterable[SearchResult]:
        ...


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in TRACKING_PARAMS
        ]
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            query,
            "",
        )
    )
