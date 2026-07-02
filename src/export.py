from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def export_records(records: list[dict], output_base: str = "output/companies") -> None:
    base = Path(output_base)
    base.parent.mkdir(parents=True, exist_ok=True)

    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    xlsx_path = base.with_suffix(".xlsx")

    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    frame = pd.DataFrame(records)
    frame.to_csv(csv_path, index=False)
    frame.to_excel(xlsx_path, index=False)
