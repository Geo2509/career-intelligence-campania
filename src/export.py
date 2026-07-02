from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


EXPORT_COLUMNS = [
    "Company",
    "Domain",
    "City",
    "Region",
    "Category",
    "Website",
    "Contact",
    "Career",
    "Email",
    "Phone",
    "Score",
    "Confidence",
    "Status",
    "Queries",
    "Engines",
    "Why Relevant",
    "Next Action",
]


def _first(values: object) -> str:
    if isinstance(values, list):
        return values[0] if values else ""
    return str(values or "")


def _join(values: object) -> str:
    if isinstance(values, list):
        return "; ".join(str(value) for value in values if value)
    return str(values or "")


def records_to_export_rows(records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        rows.append(
            {
                "Company": record.get("company", ""),
                "Domain": record.get("domain", ""),
                "City": record.get("city", ""),
                "Region": record.get("region", ""),
                "Category": record.get("category", ""),
                "Website": record.get("website") or record.get("url", ""),
                "Contact": record.get("contact_url", ""),
                "Career": record.get("career_url", ""),
                "Email": _first(record.get("emails")),
                "Phone": _first(record.get("phones")),
                "Score": record.get("score", 0),
                "Confidence": record.get("confidence", 0),
                "Status": record.get("status", ""),
                "Queries": _join(record.get("queries")),
                "Engines": _join(record.get("engines")),
                "Why Relevant": record.get("why_relevant", ""),
                "Next Action": record.get("next_action", ""),
            }
        )
    return rows


def export_records(records: list[dict], output_base: str = "output/companies") -> None:
    base = Path(output_base)
    base.parent.mkdir(parents=True, exist_ok=True)

    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    xlsx_path = base.with_suffix(".xlsx")

    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    frame = pd.DataFrame(records_to_export_rows(records), columns=EXPORT_COLUMNS)
    frame.to_csv(csv_path, index=False)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Targets", index=False)
