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
    "Industry",
    "Business Type",
    "Company Size",
    "Website",
    "Contact",
    "Career",
    "Email",
    "Phone",
    "Logistics Score",
    "Office Score",
    "Career Page",
    "HR Email",
    "LinkedIn",
    "Facebook",
    "Qualification",
    "Score",
    "Confidence",
    "Discovery Confidence",
    "Discovery Confidence Level",
    "Website Type",
    "Website Type Confidence",
    "Website Type Reasons",
    "Discovery Strategy",
    "Original Query",
    "Search Engine",
    "Status",
    "Queries",
    "Engines",
    "Why Relevant",
    "Positive Reasons",
    "Negative Reasons",
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
                "Industry": record.get("industry", ""),
                "Business Type": _join(record.get("business_type")),
                "Company Size": record.get("company_size", ""),
                "Website": record.get("website") or record.get("url", ""),
                "Contact": record.get("contact_url", ""),
                "Career": record.get("career_url", ""),
                "Email": _first(record.get("emails")),
                "Phone": _first(record.get("phones")),
                "Logistics Score": record.get("logistics_score", 0),
                "Office Score": record.get("office_score", 0),
                "Career Page": record.get("career_page", ""),
                "HR Email": record.get("hr_email", ""),
                "LinkedIn": record.get("linkedin", ""),
                "Facebook": record.get("facebook", ""),
                "Qualification": record.get("qualification", ""),
                "Score": record.get("score", 0),
                "Confidence": record.get("confidence", 0),
                "Discovery Confidence": record.get("discovery_confidence", 0),
                "Discovery Confidence Level": record.get("discovery_confidence_level", ""),
                "Website Type": record.get("website_type", ""),
                "Website Type Confidence": record.get("website_type_confidence", record.get("website_type_score", "")),
                "Website Type Reasons": _join(record.get("website_type_reasons", []) or record.get("website_type_reasons", [])),
                "Website Type Score": record.get("website_type_score", ""),
                "Discovery Strategy": _join(record.get("strategies") or [record.get("strategy", "")]),
                "Original Query": _first(record.get("queries")),
                "Search Engine": _join(record.get("engines")),
                "Status": record.get("status", ""),
                "Queries": _join(record.get("queries")),
                "Engines": _join(record.get("engines")),
                "Why Relevant": record.get("why_relevant", ""),
                "Positive Reasons": _join(record.get("positive_reasons")),
                "Negative Reasons": _join(record.get("negative_reasons")),
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
