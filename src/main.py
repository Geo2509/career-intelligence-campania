from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Callable

import yaml

from .company_extractor import extract_companies, is_aggregator, load_aggregators
from .company_extractor import excluded_domain_type, load_excluded_domain_classes
from .dedupe import dedupe_companies
from .discovery import discover_search_results
from .discovery_optimization import (
    STRATEGY_RANKING_PATH,
    build_discovery_recommendations,
    build_historical_strategy_ranking,
    build_query_performance_report,
    print_query_ranking,
    print_recommendations,
    print_strategy_ranking,
    update_discovery_learning,
    write_discovery_recommendations,
    write_query_performance_report,
)
from .engine_performance import (
    build_engine_performance_report,
    print_engine_report,
    write_engine_performance_report,
)
from .employer_intelligence import enrich_companies
from .employer_validator import filter_valid_employers, validate_employer
from .export import export_records
from .history import update_history
from .query_generator import build_discovery_hash, generate_queries
from .scorer import score_companies
from .search.cache import CACHE_VERSION
from .strategy_performance import (
    build_strategy_ranking,
    build_strategy_performance_report,
    print_strategy_report,
    write_strategy_performance_report,
)
from .validation import build_validation_report, print_validation_report, write_validation_report
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
    queries_by_strategy: dict[str, int] = field(default_factory=dict)
    results_by_strategy: dict[str, int] = field(default_factory=dict)
    companies_analysed: int = 0
    industries_detected: int = 0
    logistics_companies: int = 0
    back_office_companies: int = 0
    hr_emails_found: int = 0
    excellent_matches: int = 0
    good_matches: int = 0
    ignored_companies: int = 0
    skipped_before_profiling: int = 0
    skipped_reason_counts: dict[str, int] | None = None
    profile_time_total: float = 0.0
    profile_time_average: float = 0.0


def load_negative_keywords(path: str = "configs/negative_keywords.yaml") -> list[str]:
    return (yaml.safe_load(Path(path).read_text()) or {}).get("negative_keywords", [])


def discovery_confidence_level(confidence: int) -> str:
    if confidence >= 80:
        return "High"
    if confidence >= 60:
        return "Medium"
    if confidence >= 40:
        return "Low"
    return "Ignore"


def run(
    limit_queries: int | None,
    profile: bool,
    output_base: str,
    search_engines_path: str = "configs/search_engines.yaml",
    history_path: str = "history/companies_history.json",
    verbose: bool = False,
    max_profile_companies: int | None = None,
    profile_only_qualified: bool | None = False,
    profile_timeout: int = 15,
    engine: str = "duckduckgo",
) -> tuple[list[dict], RunStats]:
    started = time.monotonic()
    progress = print if verbose else None
    search_run = discover_search_results(
        search_engines_path=search_engines_path,
        limit_queries=limit_queries,
        engine=engine,
        progress=progress,
    )
    raw_results = [result.to_dict() for result in search_run.results]
    search_stats = search_run.stats
    discovery_hash = search_run.discovery_hash
    all_queries = search_run.all_queries
    executed_queries = search_run.executed_queries

    log(progress, "")
    log(progress, "Filtering aggregators...")
    companies = extract_companies(
        raw_results,
        negative_keywords=load_negative_keywords(),
        aggregators=load_aggregators(),
    )
    after_filter = len(companies)
    after_filter_companies = list(companies)
    log(progress, f"Remaining companies: {after_filter}")

    log(progress, "Deduplicating companies...")
    companies = dedupe_companies(companies)
    companies = filter_valid_employers(companies, allow_unconfirmed=True)
    log(progress, f"Unique companies: {len(companies)}")

    if profile:
        profile_candidates, skipped_reason_counts = select_companies_for_profiling(
            companies,
            max_profile_companies=max_profile_companies,
            profile_only_qualified=profile_only_qualified,
        )
        log(
            progress,
            f"Pre-profile filter: {len(profile_candidates)} selected, "
            f"{len(companies) - len(profile_candidates)} skipped",
        )
        profiled = []
        profile_started = time.monotonic()
        for index, company in enumerate(profile_candidates, start=1):
            log(
                progress,
                f"Profiling company {index}/{len(profile_candidates)}: "
                f"{company.get('domain', company.get('company', ''))}",
            )
            profile_data = profile_website(
                company.get("website") or company["url"],
                timeout=profile_timeout,
            ).to_dict()
            profiled.append(validate_employer({**company, **profile_data}))
        profile_time_total = round(time.monotonic() - profile_started, 2)
        profile_time_average = round(profile_time_total / len(profiled), 2) if profiled else 0.0
        profiled_count = len(profiled)
        profiled_domains = {profiled_company.get("domain", "") for profiled_company in profiled}
        companies = profiled + [
            validate_employer(company)
            for company in companies
            if company.get("domain") not in profiled_domains
        ]
    else:
        log(progress, "Skipping website profiling (--no-profile).")
        companies = [validate_employer(company) for company in companies]
        skipped_reason_counts = {}
        profile_time_total = 0.0
        profile_time_average = 0.0
        profiled_count = 0
        profiled_domains = set()

    log(progress, "Analysing employer intelligence...")
    companies = enrich_companies(companies)
    log(progress, "Scoring companies...")
    scored = score_companies(companies)
    with_history = update_history(scored, history_path)
    strategy_report = build_strategy_performance_report(
        all_queries=all_queries,
        search_stats=search_stats,
        raw_results=raw_results,
        after_filter_companies=after_filter_companies,
        final_companies=with_history,
        profiled_domains=profiled_domains,
    )
    write_strategy_performance_report(strategy_report)
    engine_report = build_engine_performance_report(
        search_stats=search_stats,
        raw_results=raw_results,
        final_companies=with_history,
    )
    write_engine_performance_report(engine_report)
    current_strategy_ranking = build_strategy_ranking(strategy_report)
    query_performance = build_query_performance_report(
        all_queries=all_queries,
        raw_results=raw_results,
        final_companies=with_history,
        profiled_domains=profiled_domains,
    )
    write_query_performance_report(query_performance)
    log(progress, "Exporting Excel...")
    export_records(with_history, output_base)
    log(progress, "Done.")
    run_stats = RunStats(
        queries_generated=len(all_queries),
        queries_executed=len(executed_queries),
        raw_results=len(raw_results),
        after_aggregator_filter=after_filter,
        unique_companies=len(companies),
        profiled_companies=profiled_count,
        emails_found=sum(1 for company in with_history if company.get("emails")),
        career_pages_found=sum(1 for company in with_history if company.get("has_careers_page")),
        exported_rows=len(with_history),
        run_duration=round(time.monotonic() - started, 2),
        ddg_results=search_stats.ddg_results,
        serpapi_results=search_stats.serpapi_results,
        search_errors=search_stats.search_errors,
        cache_hits=search_stats.cache_hits,
        cache_misses=search_stats.cache_misses,
        queries_by_strategy=search_stats.queries_by_strategy,
        results_by_strategy=search_stats.results_by_strategy,
        companies_analysed=len(companies),
        industries_detected=sum(1 for company in companies if company.get("industry") and company.get("industry") != "Unknown"),
        logistics_companies=sum(1 for company in companies if company.get("logistics_score", 0) > 0),
        back_office_companies=sum(1 for company in companies if "Back Office" in company.get("office_signals", [])),
        hr_emails_found=sum(1 for company in companies if company.get("hr_email")),
        excellent_matches=sum(1 for company in companies if company.get("qualification") == "Excellent Match"),
        good_matches=sum(1 for company in companies if company.get("qualification") == "Good Match"),
        ignored_companies=sum(1 for company in companies if company.get("next_action") == "Ignore"),
        skipped_before_profiling=len(companies) - profiled_count,
        skipped_reason_counts=skipped_reason_counts,
        profile_time_total=profile_time_total,
        profile_time_average=profile_time_average,
    )

    run_metadata = {
        "generated_queries": len(all_queries),
        "executed_queries": len(executed_queries),
        "cached_queries": search_stats.cached_queries,
        "live_queries": search_stats.live_queries,
        "cache_hits": search_stats.cache_hits,
        "cache_misses": search_stats.cache_misses,
        "raw_results": len(raw_results),
        "unique_companies": run_stats.unique_companies,
        "profiled_companies": run_stats.profiled_companies,
        "run_duration": run_stats.run_duration,
    }
    Path("output").mkdir(parents=True, exist_ok=True)
    Path("output/run_metadata.json").write_text(json.dumps(run_metadata, ensure_ascii=False, indent=2))

    raw_query_counts: dict[str, int] = {}
    for result in raw_results:
        raw_query = result.get("query", "")
        if raw_query:
            raw_query_counts[raw_query] = raw_query_counts.get(raw_query, 0) + 1

    company_query_counts: dict[str, int] = {}
    for company in companies:
        query = company.get("query", "")
        if query:
            company_query_counts[query] = company_query_counts.get(query, 0) + 1

    queries_with_zero_results = [query for query, count in search_stats.query_results.items() if count == 0]
    queries_with_only_excluded_domains = sorted(
        query for query, raw_count in raw_query_counts.items() if raw_count > 0 and company_query_counts.get(query, 0) == 0
    )

    all_generated_queries, _ = generate_queries()
    configured_strategies = {query.strategy for query in all_generated_queries}
    executed_strategies = {query.strategy for query in executed_queries}
    discovery_health = {
        "strategies_configured": len(configured_strategies),
        "strategies_used": len(executed_strategies),
        "unused_strategies": sorted(list(configured_strategies - executed_strategies)),
        "queries_never_executed": [query.query for query in all_generated_queries if query not in executed_queries],
        "queries_with_zero_results": sorted(queries_with_zero_results),
        "queries_with_only_excluded_domains": queries_with_only_excluded_domains,
    }
    Path("output/discovery_health.json").write_text(json.dumps(discovery_health, ensure_ascii=False, indent=2))
    learning = update_discovery_learning(
        strategy_ranking=current_strategy_ranking,
        query_performance=query_performance,
    )
    strategy_ranking = build_historical_strategy_ranking(learning, fallback_ranking=current_strategy_ranking)
    STRATEGY_RANKING_PATH.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY_RANKING_PATH.write_text(json.dumps(strategy_ranking, ensure_ascii=False, indent=2))
    recommendations = build_discovery_recommendations(
        strategy_ranking=strategy_ranking,
        query_performance=query_performance,
        discovery_health=discovery_health,
        strategy_performance=strategy_report,
        learning=learning,
    )
    write_discovery_recommendations(recommendations)
    validation_report = build_validation_report(
        records=with_history,
        run_stats=run_stats,
        engine_performance=engine_report,
        strategy_ranking=strategy_ranking,
        query_performance=query_performance,
        discovery_recommendations=recommendations,
    )
    write_validation_report(validation_report)
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


def audit_cache(
    search_config: str = "configs/search_engines.yaml",
    discovery_path: str = "configs/discovery.yaml",
) -> dict:
    config = yaml.safe_load(Path(search_config).read_text()) or {}
    cache_config = config.get("cache", {})
    cache_path = Path(cache_config.get("path", "output/cache/search_results.json"))
    current_hash = build_discovery_hash(discovery_path)
    cache_data = {}
    cache_entries = 0
    cache_discovery_hashes: list[str] = []
    obsolete_entries = 0
    queries_not_matching_current: list[str] = []

    if cache_path.exists():
        try:
            cache_data = json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            cache_data = {}

    cache_hash = cache_data.get("discovery_hash", "")
    cache_discovery_hashes = [cache_hash] if cache_hash else []
    records = cache_data.get("records", {}) if isinstance(cache_data.get("records", {}), dict) else {}
    cache_entries = len(records)
    if cache_hash != current_hash or cache_data.get("discovery_version") != CACHE_VERSION:
        obsolete_entries = cache_entries

    current_queries = {query.query for query in generate_queries(discovery_path=discovery_path)[0]}
    for key in records:
        query = key.split("::", 1)[1] if "::" in key else key
        if query not in current_queries:
            queries_not_matching_current.append(query)

    audit = {
        "cache_entries": cache_entries,
        "obsolete_cache_entries": obsolete_entries,
        "current_discovery_hash": current_hash,
        "cache_discovery_hashes": cache_discovery_hashes,
        "queries_not_matching_current_discovery": sorted(queries_not_matching_current),
    }
    Path("output").mkdir(parents=True, exist_ok=True)
    Path("output/cache_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit


def log(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)


def select_companies_for_profiling(
    companies: list[dict],
    max_profile_companies: int | None = None,
    profile_only_qualified: bool = False,
) -> tuple[list[dict], dict[str, int]]:
    selected: list[dict] = []
    skipped: dict[str, int] = {
        "skipped_domain_excluded": 0,
        "skipped_staffing_agency": 0,
        "skipped_public_sector": 0,
        "skipped_directory": 0,
        "skipped_media": 0,
        "skipped_education": 0,
    }
    excluded_classes = load_excluded_domain_classes()

    for company in companies:
        reason = profile_skip_reason(company, excluded_classes, profile_only_qualified)
        if reason:
            if reason.startswith("skipped_") and reason != "skipped_domain_excluded":
                skipped["skipped_domain_excluded"] = skipped.get("skipped_domain_excluded", 0) + 1
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        if max_profile_companies is not None and len(selected) >= max_profile_companies:
            skipped["max_profile_companies"] = skipped.get("max_profile_companies", 0) + 1
            continue
        selected.append(company)
    return selected, skipped


def profile_skip_reason(
    company: dict,
    excluded_classes: dict[str, str] | None = None,
    profile_only_qualified: bool = False,
) -> str:
    excluded_type = excluded_domain_type(company.get("domain", ""), excluded_classes or load_excluded_domain_classes())
    if excluded_type:
        return f"skipped_{excluded_type}"
    if profile_only_qualified and company.get("qualification") in {"Low Match", "Not Relevant"}:
        return "not_qualified"
    if not weak_employer_evidence(company):
        return "no_weak_employer_evidence"
    return ""


def weak_employer_evidence(company: dict) -> bool:
    text = " ".join(str(company.get(key, "")) for key in ("title", "snippet", "domain", "url")).lower()
    domain = company.get("domain", "").lower()

    company_service_evidence = any(
        term in text
        for term in (
            "azienda",
            "srl",
            "s.r.l",
            "spa",
            "s.p.a",
            "società",
            "chi siamo",
            "i nostri servizi",
            "produzione",
            "software",
            "studio",
        )
    )
    logistics_office_evidence = any(
        term in text
        for term in (
            "logistica",
            "spedizioni",
            "trasporti",
            "import",
            "export",
            "dogana",
            "documenti",
            "documentazione",
            "back office",
        )
    )
    contact_career_evidence = bool(company.get("contact_url") or company.get("career_url")) or any(
        term in text for term in ("contatti", "lavora con noi", "careers")
    )
    business_evidence = any(
        term in text
        for term in (
            "b2b",
            "business",
            "fornitore",
            "produttore",
            "distributore",
            "service provider",
            "soluzioni per aziende",
        )
    )
    url_evidence = domain.endswith(".it") and not any(
        marker in domain for marker in ("blog", "news", "forum", "directory", "portal")
    )

    return (
        (company_service_evidence and url_evidence)
        or logistics_office_evidence
        or contact_career_evidence
        or business_evidence
    )


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
    print(f"Queries by strategy: {stats.queries_by_strategy}")
    print(f"Results by strategy: {stats.results_by_strategy}")
    print(f"Run duration: {stats.run_duration}s")
    print(f"Companies analysed: {stats.companies_analysed}")
    print(f"Industries detected: {stats.industries_detected}")
    print(f"Logistics companies: {stats.logistics_companies}")
    print(f"Back office companies: {stats.back_office_companies}")
    print(f"Career pages found: {stats.career_pages_found}")
    print(f"HR emails found: {stats.hr_emails_found}")
    print(f"Excellent matches: {stats.excellent_matches}")
    print(f"Good matches: {stats.good_matches}")
    print(f"Ignored companies: {stats.ignored_companies}")
    print(f"Skipped before profiling: {stats.skipped_before_profiling}")
    print(f"Skipped reason counts: {stats.skipped_reason_counts or {}}")
    print(f"Profile time total: {stats.profile_time_total}s")
    print(f"Profile time average: {stats.profile_time_average}s")


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
    parser.add_argument("--engine", choices=("duckduckgo", "serpapi", "all"), default="duckduckgo")
    parser.add_argument("--history", default="history/companies_history.json")
    parser.add_argument("--quiet", action="store_true", help="Hide live progress output.")
    parser.add_argument("--max-profile-companies", type=int, default=None)
    parser.add_argument("--profile-only-qualified", action="store_true")
    parser.add_argument("--profile-timeout", type=int, default=15)
    parser.add_argument(
        "--cache-audit",
        action="store_true",
        help="Audit the search cache against the current discovery configuration.",
    )
    parser.add_argument(
        "--strategy-report",
        action="store_true",
        help="Print a readable strategy performance table after the run.",
    )
    parser.add_argument(
        "--strategy-ranking",
        action="store_true",
        help="Print ranked discovery strategies after the run.",
    )
    parser.add_argument(
        "--query-ranking",
        action="store_true",
        help="Print ranked discovery queries after the run.",
    )
    parser.add_argument(
        "--recommend-discovery",
        action="store_true",
        help="Print discovery optimization recommendations after the run.",
    )
    parser.add_argument(
        "--engine-report",
        action="store_true",
        help="Print search engine performance after the run.",
    )
    parser.add_argument(
        "--validation-report",
        action="store_true",
        help="Print validation quality summary after the run.",
    )
    args = parser.parse_args()

    if args.cache_audit:
        audit = audit_cache(args.search_config)
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        return

    records, stats = run(
        args.limit_queries,
        args.profile,
        args.output,
        args.search_config,
        args.history,
        verbose=not args.quiet,
        max_profile_companies=args.max_profile_companies,
        profile_only_qualified=args.profile_only_qualified,
        profile_timeout=args.profile_timeout,
        engine=args.engine,
    )
    print(f"Exported {len(records)} companies to {args.output}.json/.csv/.xlsx")
    print_run_stats(stats)
    if args.strategy_report:
        report_path = Path("output/strategy_performance.json")
        if report_path.exists():
            print("")
            print_strategy_report(json.loads(report_path.read_text()))
    if args.strategy_ranking:
        report_path = Path("output/strategy_ranking.json")
        if report_path.exists():
            print("")
            print_strategy_ranking(json.loads(report_path.read_text()))
    if args.query_ranking:
        report_path = Path("output/query_performance.json")
        if report_path.exists():
            print("")
            print_query_ranking(json.loads(report_path.read_text()))
    if args.recommend_discovery:
        report_path = Path("output/discovery_recommendations.json")
        if report_path.exists():
            print("")
            print_recommendations(json.loads(report_path.read_text()))
    if args.engine_report:
        report_path = Path("output/engine_performance.json")
        if report_path.exists():
            print("")
            print_engine_report(json.loads(report_path.read_text()))
    if args.validation_report:
        report_path = Path("output/validation_report.json")
        if report_path.exists():
            print("")
            print_validation_report(json.loads(report_path.read_text()))


if __name__ == "__main__":
    main()
