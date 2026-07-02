from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_history(path: str | Path = "history/companies_history.json") -> dict:
    history_path = Path(path)
    if not history_path.exists():
        return {}
    try:
        data = json.loads(history_path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def update_history(companies: list[dict], path: str | Path = "history/companies_history.json") -> list[dict]:
    history_path = Path(path)
    history = load_history(history_path)
    timestamp = _now()
    updated_companies: list[dict] = []

    for company in companies:
        domain = company.get("domain", "")
        if not domain:
            continue
        previous = history.get(domain)
        queries = sorted(set((previous or {}).get("queries", []) + company.get("queries", [])))
        engines = sorted(set((previous or {}).get("engines", []) + company.get("engines", [])))
        status = "NEW"
        if previous:
            status = "UPDATED" if _changed(previous, company) else "SEEN"

        record = {
            "first_seen": (previous or {}).get("first_seen", timestamp),
            "last_seen": timestamp,
            "status": status,
            "times_found": int((previous or {}).get("times_found", 0)) + 1,
            "queries": queries,
            "engines": engines,
            "score": company.get("score", 0),
            "confidence": company.get("confidence", 0),
            "email": first_value(company.get("emails")),
            "phone": first_value(company.get("phones")),
        }
        history[domain] = record
        enriched = dict(company)
        enriched.update(record)
        updated_companies.append(enriched)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    return updated_companies


def _changed(previous: dict, company: dict) -> bool:
    return (
        previous.get("score") != company.get("score")
        or previous.get("confidence") != company.get("confidence")
        or previous.get("email") != first_value(company.get("emails"))
        or previous.get("phone") != first_value(company.get("phones"))
    )


def first_value(values: object) -> str:
    if isinstance(values, list) and values:
        return str(values[0])
    if isinstance(values, str):
        return values
    return ""
