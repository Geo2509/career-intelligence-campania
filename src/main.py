from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .company_extractor import extract_companies
from .dedupe import dedupe_companies
from .discovery import discover_companies
from .export import export_records
from .scorer import score_companies
from .website_profiler import profile_website


def load_negative_keywords(path: str = "configs/negative_keywords.yaml") -> list[str]:
    return (yaml.safe_load(Path(path).read_text()) or {}).get("negative_keywords", [])


def run(limit_queries: int | None, profile: bool, output_base: str) -> list[dict]:
    raw_results = discover_companies(limit_queries=limit_queries)
    companies = extract_companies(raw_results, load_negative_keywords())
    companies = dedupe_companies(companies)

    if profile:
        profiled = []
        for company in companies:
            profile_data = profile_website(company["url"]).to_dict()
            profiled.append({**company, **profile_data})
        companies = profiled

    scored = score_companies(companies)
    export_records(scored, output_base)
    return scored


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover direct employer contacts in Campania.")
    parser.add_argument("--limit-queries", type=int, default=10)
    parser.add_argument("--profile", action="store_true", help="Fetch company websites and extract contacts.")
    parser.add_argument("--output", default="output/companies")
    args = parser.parse_args()

    records = run(args.limit_queries, args.profile, args.output)
    print(f"Exported {len(records)} companies to {args.output}.json/.csv/.xlsx")


if __name__ == "__main__":
    main()
