from __future__ import annotations

import re


WHATSAPP_RE = re.compile(r"(?:wa\.me/|whatsapp)", re.IGNORECASE)


def detect_contacts(company: dict) -> dict:
    emails = company.get("emails") or []
    phones = company.get("phones") or []
    page_text = str(company.get("page_text", ""))
    whatsapp = ""
    if WHATSAPP_RE.search(page_text):
        whatsapp = "present"
    return {
        "general_email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "whatsapp": whatsapp,
        "linkedin": company.get("linkedin", ""),
        "facebook": company.get("facebook", ""),
    }
