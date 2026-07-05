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
from .engine_contribution import (
    build_engine_contribution_report,
    print_engine_contribution_report,
    write_engine_contribution_report,
)
from .engine_performance import (
    build_engine_performance_report,
    print_engine_report,
    write_engine_performance_report,
)
from .employer_intelligence import enrich_companies
from .employer_validator import filter_valid_employers, validate_employer
from .export import export_records
from .export_filter import apply_final_export_filter, write_export_filter_report
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
from .website_classifier import classify_company, post_profile_reclassify_companies


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
    # website type statistics
    website_type_company: int = 0
    website_type_staffing_agency: int = 0
    website_type_job_board: int = 0
    website_type_directory: int = 0
    website_type_marketplace: int = 0
    website_type_government: int = 0
    website_type_municipality: int = 0
    website_type_education: int = 0
    website_type_university: int = 0
    website_type_school: int = 0
    website_type_media: int = 0
    website_type_news: int = 0
    website_type_blog: int = 0
    website_type_association: int = 0
    website_type_nonprofit: int = 0
    website_type_healthcare: int = 0
    website_type_unknown: int = 0
    skipped_website_type: int = 0
    post_reclassified_count: int = 0
    post_reclassified_to_staffing_agency: int = 0
    post_reclassified_to_job_board: int = 0
    post_reclassified_to_directory: int = 0
    post_reclassified_to_public_sector: int = 0
    post_reclassified_to_media: int = 0
    post_reclassified_to_non_employer: int = 0
    send_cv_removed_by_reclassification: int = 0
    priority_80_plus: int = 0
    priority_60_79: int = 0
    priority_40_59: int = 0
    priority_below_40: int = 0
    average_priority: float = 0.0
    top_priority_employer: str = ""
    removed_by_export_filter: int = 0
    removed_social_media: int = 0
    removed_reviews: int = 0
    removed_travel: int = 0
    removed_platforms: int = 0
    removed_non_employers: int = 0
    removed_blacklist: int = 0


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
    # Classify website type before profiling to avoid profiling non-employer sites
    for c in companies:
        wtype, wconf, wreasons = classify_company(c)
        c["website_type"] = wtype
        c["website_type_confidence"] = wconf
        c["website_type_score"] = wconf
        c["website_type_reasons"] = wreasons
        c["website_type_initial"] = wtype
        c["website_type_initial_confidence"] = wconf
        c["website_type_final"] = wtype
        c["website_type_final_confidence"] = wconf
        c["website_type_final_reasons"] = wreasons
    # Compute website type stats snapshot (counts)
    website_types = [c.get("website_type", "unknown") for c in companies]
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
    log(progress, "Reclassifying websites with post-profile evidence...")
    companies, post_reclassification_stats = post_profile_reclassify_companies(companies)
    website_types = [c.get("website_type", "unknown") for c in companies]
    log(progress, "Scoring companies...")
    scored = score_companies(companies)
    log(progress, "Applying final export filter...")
    filtered_companies, export_filter_report = apply_final_export_filter(scored)
    write_export_filter_report(export_filter_report)
    with_history = update_history(filtered_companies, history_path)
    priority_scores = [int(company.get("employer_priority_score", 0) or 0) for company in with_history]
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
    engine_contribution_report = build_engine_contribution_report(
        raw_results=raw_results,
        after_filter_companies=after_filter_companies,
        final_companies=with_history,
        profiled_domains=profiled_domains,
    )
    write_engine_contribution_report(engine_contribution_report)
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
        queries_executed=search_stats.queries_executed,
        raw_results=len(raw_results),
        after_aggregator_filter=after_filter,
        unique_companies=len(with_history),
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
        companies_analysed=len(with_history),
        industries_detected=sum(1 for company in with_history if company.get("industry") and company.get("industry") != "Unknown"),
        logistics_companies=sum(1 for company in with_history if company.get("logistics_score", 0) > 0),
        back_office_companies=sum(1 for company in with_history if "Back Office" in company.get("office_signals", [])),
        hr_emails_found=sum(1 for company in with_history if company.get("hr_email")),
        excellent_matches=sum(1 for company in with_history if company.get("qualification") == "Excellent Match"),
        good_matches=sum(1 for company in with_history if company.get("qualification") == "Good Match"),
        ignored_companies=sum(1 for company in with_history if company.get("next_action") == "Ignore"),
        skipped_before_profiling=len(with_history) - profiled_count,
        skipped_reason_counts=skipped_reason_counts,
        profile_time_total=profile_time_total,
        profile_time_average=profile_time_average,
        website_type_company=sum(1 for t in website_types if t == "company"),
        website_type_staffing_agency=sum(1 for t in website_types if t == "staffing_agency"),
        website_type_job_board=sum(1 for t in website_types if t == "job_board"),
        website_type_directory=sum(1 for t in website_types if t == "directory"),
        website_type_marketplace=sum(1 for t in website_types if t == "marketplace"),
        website_type_government=sum(1 for t in website_types if t == "government"),
        website_type_municipality=sum(1 for t in website_types if t == "municipality"),
        website_type_education=sum(1 for t in website_types if t == "education"),
        website_type_university=sum(1 for t in website_types if t == "university"),
        website_type_school=sum(1 for t in website_types if t == "school"),
        website_type_media=sum(1 for t in website_types if t == "media"),
        website_type_news=sum(1 for t in website_types if t == "news"),
        website_type_blog=sum(1 for t in website_types if t == "blog"),
        website_type_association=sum(1 for t in website_types if t == "association"),
        website_type_nonprofit=sum(1 for t in website_types if t == "nonprofit"),
        website_type_healthcare=sum(1 for t in website_types if t == "healthcare"),
        website_type_unknown=sum(1 for t in website_types if not t or t == "unknown"),
        skipped_website_type=0,
        post_reclassified_count=post_reclassification_stats["post_reclassified_count"],
        post_reclassified_to_staffing_agency=post_reclassification_stats["post_reclassified_to_staffing_agency"],
        post_reclassified_to_job_board=post_reclassification_stats["post_reclassified_to_job_board"],
        post_reclassified_to_directory=post_reclassification_stats["post_reclassified_to_directory"],
        post_reclassified_to_public_sector=post_reclassification_stats["post_reclassified_to_public_sector"],
        post_reclassified_to_media=post_reclassification_stats["post_reclassified_to_media"],
        post_reclassified_to_non_employer=post_reclassification_stats["post_reclassified_to_non_employer"],
        send_cv_removed_by_reclassification=post_reclassification_stats["send_cv_removed_by_reclassification"],
        priority_80_plus=sum(1 for score in priority_scores if score >= 80),
        priority_60_79=sum(1 for score in priority_scores if 60 <= score <= 79),
        priority_40_59=sum(1 for score in priority_scores if 40 <= score <= 59),
        priority_below_40=sum(1 for score in priority_scores if score < 40),
        average_priority=round(sum(priority_scores) / len(priority_scores), 2) if priority_scores else 0.0,
        top_priority_employer=with_history[0].get("company", "") if with_history else "",
        removed_by_export_filter=export_filter_report["removed_by_export_filter"],
        removed_social_media=export_filter_report["removed_social_media"],
        removed_reviews=export_filter_report["removed_reviews"],
        removed_travel=export_filter_report["removed_travel"],
        removed_platforms=export_filter_report["removed_platforms"],
        removed_non_employers=export_filter_report["removed_non_employers"],
        removed_blacklist=export_filter_report["removed_blacklist"],
    )

    run_metadata = {
        "generated_queries": len(all_queries),
        "executed_queries": search_stats.queries_executed,
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
        parts = key.split("::", 2)
        query = parts[-1] if len(parts) > 1 else key
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
    # Skip based on website type classification
    wtype = (company.get("website_type") or "").lower()
    if wtype == "staffing_agency":
        return "skipped_staffing_agency"
    if wtype in {
        "job_board",
        "directory",
        "marketplace",
        "government",
        "municipality",
        "education",
        "university",
        "school",
        "media",
        "news",
        "blog",
        "association",
        "nonprofit",
        "healthcare",
    }:
        return "skipped_website_type"
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
    print(f"Post-profile reclassified: {stats.post_reclassified_count}")
    print(f"Post-profile staffing agencies: {stats.post_reclassified_to_staffing_agency}")
    print(f"Post-profile job boards: {stats.post_reclassified_to_job_board}")
    print(f"Post-profile directories: {stats.post_reclassified_to_directory}")
    print(f"Post-profile public sector: {stats.post_reclassified_to_public_sector}")
    print(f"Post-profile media: {stats.post_reclassified_to_media}")
    print(f"Post-profile non-employers: {stats.post_reclassified_to_non_employer}")
    print(f"Send CV removed by reclassification: {stats.send_cv_removed_by_reclassification}")
    print(f"Priority >=80: {stats.priority_80_plus}")
    print(f"Priority 60-79: {stats.priority_60_79}")
    print(f"Priority 40-59: {stats.priority_40_59}")
    print(f"Priority <40: {stats.priority_below_40}")
    print(f"Average priority: {stats.average_priority}")
    print(f"Top priority employer: {stats.top_priority_employer}")
    print(f"Removed by export filter: {stats.removed_by_export_filter}")
    print(f"Removed social media: {stats.removed_social_media}")
    print(f"Removed reviews: {stats.removed_reviews}")
    print(f"Removed travel: {stats.removed_travel}")
    print(f"Removed platforms: {stats.removed_platforms}")
    print(f"Removed non-employers: {stats.removed_non_employers}")
    print(f"Removed blacklist: {stats.removed_blacklist}")


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
        "--engine-contribution-report",
        action="store_true",
        help="Print search engine overlap and unique contribution after the run.",
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
    if args.engine_contribution_report:
        report_path = Path("output/engine_contribution.json")
        if report_path.exists():
            print("")
            print_engine_contribution_report(json.loads(report_path.read_text()))
    if args.validation_report:
        report_path = Path("output/validation_report.json")
        if report_path.exists():
            print("")
            print_validation_report(json.loads(report_path.read_text()))


if __name__ == "__main__":
    main()
