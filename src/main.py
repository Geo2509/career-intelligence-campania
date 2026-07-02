from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import yaml

from .company_extractor import extract_companies, load_aggregators
from .dedupe import dedupe_companies
from .discovery import discover_search_results
from .employer_validator import filter_valid_employers, validate_employer
from .export import export_records
from .history import update_history
from .scorer import score_companies
from .website_profiler import profile_website


@dataclass
class RunStats:
    queries_generated: int = 0
    queries_executed: int = 0
    raw_results: int = 0
    after_aggregator_filter: int = 0
    unique_companies: int = 0
    profiled_companies: int = 0
    emails_found: int = 0
    career_pages_found: int = 0
    exported_rows: int = 0
    run_duration: float = 0.0
    ddg_results: int = 0
    serpapi_results: int = 0
    search_errors: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


def load_negative_keywords(path: str = "configs/negative_keywords.yaml") -> list[str]:
    return (yaml.safe_load(Path(path).read_text()) or {}).get("negative_keywords", [])


def run(
    limit_queries: int | None,
    profile: bool,
    output_base: str,
    search_engines_path: str = "configs/search_engines.yaml",
    history_path: str = "history/companies_history.json",
) -> tuple[list[dict], RunStats]:
    started = time.monotonic()
    search_run = discover_search_results(search_engines_path=search_engines_path, limit_queries=limit_queries)
    raw_results = [result.to_dict() for result in search_run.results]
    search_stats = search_run.stats

    companies = extract_companies(
        raw_results,
        negative_keywords=load_negative_keywords(),
        aggregators=load_aggregators(),
    )
    after_filter = len(companies)
    companies = dedupe_companies(companies)
    companies = filter_valid_employers(companies, allow_unconfirmed=True)

    if profile:
        profiled = []
        for company in companies:
            profile_data = profile_website(company.get("website") or company["url"]).to_dict()
            profiled.append(validate_employer({**company, **profile_data}))
        companies = profiled
    else:
        companies = [validate_employer(company) for company in companies]

    scored = score_companies(companies)
    with_history = update_history(scored, history_path)
    export_records(with_history, output_base)
    run_stats = RunStats(
        queries_generated=search_stats.queries_generated,
        queries_executed=search_stats.queries_executed,
        raw_results=len(raw_results),
        after_aggregator_filter=after_filter,
        unique_companies=len(companies),
        profiled_companies=len(companies) if profile else 0,
        emails_found=sum(1 for company in with_history if company.get("emails")),
        career_pages_found=sum(1 for company in with_history if company.get("has_careers_page")),
        exported_rows=len(with_history),
        run_duration=round(time.monotonic() - started, 2),
        ddg_results=search_stats.ddg_results,
        serpapi_results=search_stats.serpapi_results,
        search_errors=search_stats.search_errors,
        cache_hits=search_stats.cache_hits,
        cache_misses=search_stats.cache_misses,
    )
    stats_path = Path(output_base).with_name("run_stats.json")
    stats_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **asdict(run_stats),
                "search_error_details": search_stats.errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return with_history, run_stats


def print_run_stats(stats: RunStats) -> None:
    print(f"Queries generated: {stats.queries_generated}")
    print(f"Queries executed: {stats.queries_executed}")
    print(f"DDG results: {stats.ddg_results}")
    print(f"SerpAPI results: {stats.serpapi_results}")
    print(f"Search errors: {stats.search_errors}")
    print(f"Raw results: {stats.raw_results}")
    print(f"After aggregator filter: {stats.after_aggregator_filter}")
    print(f"Unique companies: {stats.unique_companies}")
    print(f"Profiled companies: {stats.profiled_companies}")
    print(f"Emails found: {stats.emails_found}")
    print(f"Career pages found: {stats.career_pages_found}")
    print(f"Exported rows: {stats.exported_rows}")
    print(f"Run duration: {stats.run_duration}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover direct employer contacts in Campania.")
    parser.add_argument("--limit-queries", type=int, default=75)
    parser.add_argument(
        "--profile",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fetch company websites and extract contacts. Use --no-profile for fast search-only runs.",
    )
    parser.add_argument("--output", default="output/campania_targets")
    parser.add_argument("--search-config", default="configs/search_engines.yaml")
    parser.add_argument("--history", default="history/companies_history.json")
    args = parser.parse_args()

    records, stats = run(args.limit_queries, args.profile, args.output, args.search_config, args.history)
    print(f"Exported {len(records)} companies to {args.output}.json/.csv/.xlsx")
    print_run_stats(stats)


if __name__ == "__main__":
    main()
