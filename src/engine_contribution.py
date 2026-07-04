from __future__ import annotations

import json
from pathlib import Path

from .strategy_performance import print_table


ENGINE_CONTRIBUTION_PATH = Path("output/engine_contribution.json")
TRACKED_ENGINES = ("duckduckgo", "serpapi")


def build_engine_contribution_report(
    *,
    raw_results: list[dict],
    after_filter_companies: list[dict],
    final_companies: list[dict],
    profiled_domains: set[str] | None = None,
) -> dict:
    profiled_domains = profiled_domains or set()
    domains_by_engine = {engine: set() for engine in TRACKED_ENGINES}
    for company in final_companies:
        domain = company.get("domain", "")
        if not domain:
            continue
        for engine in _company_engines(company):
            if engine in domains_by_engine:
                domains_by_engine[engine].add(domain)

    duckduckgo_domains = domains_by_engine["duckduckgo"]
    serpapi_domains = domains_by_engine["serpapi"]
    duckduckgo_only = duckduckgo_domains - serpapi_domains
    serpapi_only = serpapi_domains - duckduckgo_domains
    shared = duckduckgo_domains & serpapi_domains
    total_unique = len(duckduckgo_domains | serpapi_domains)

    return {
        "duckduckgo_only_companies": len(duckduckgo_only),
        "serpapi_only_companies": len(serpapi_only),
        "shared_companies": len(shared),
        "total_unique_companies": total_unique,
        "duckduckgo_unique_contribution_rate": _rate(len(duckduckgo_only), total_unique),
        "serpapi_unique_contribution_rate": _rate(len(serpapi_only), total_unique),
        "shared_rate": _rate(len(shared), total_unique),
        "engines": {
            engine: _engine_metrics(
                engine,
                raw_results=raw_results,
                after_filter_companies=after_filter_companies,
                final_companies=final_companies,
                profiled_domains=profiled_domains,
            )
            for engine in TRACKED_ENGINES
        },
    }


def write_engine_contribution_report(
    report: dict,
    path: str | Path = ENGINE_CONTRIBUTION_PATH,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def print_engine_contribution_report(report: dict) -> None:
    print("Engine Contribution")
    print("")
    print(f"DuckDuckGo only: {report.get('duckduckgo_only_companies', 0)}")
    print(f"SerpAPI only: {report.get('serpapi_only_companies', 0)}")
    print(f"Shared: {report.get('shared_companies', 0)}")
    print(f"Total: {report.get('total_unique_companies', 0)}")
    print("")
    print(f"DuckDuckGo unique contribution: {_percent(report.get('duckduckgo_unique_contribution_rate', 0))}")
    print(f"SerpAPI unique contribution: {_percent(report.get('serpapi_unique_contribution_rate', 0))}")
    print(f"Shared: {_percent(report.get('shared_rate', 0))}")

    rows = []
    for engine, metrics in sorted(report.get("engines", {}).items()):
        rows.append(
            [
                engine,
                str(metrics.get("raw_results", 0)),
                str(metrics.get("after_filter_companies", 0)),
                str(metrics.get("unique_companies", 0)),
                str(metrics.get("profiled_companies", 0)),
                str(metrics.get("good_matches", 0)),
                str(metrics.get("excellent_matches", 0)),
                str(metrics.get("send_cv_count", 0)),
                str(metrics.get("ignored_count", 0)),
                f"{float(metrics.get('precision', 0)):.2f}",
            ]
        )
    if rows:
        print("")
        print_table(
            [
                "Engine",
                "Raw",
                "After Filter",
                "Unique",
                "Profiled",
                "Good",
                "Excellent",
                "Send CV",
                "Ignored",
                "Precision",
            ],
            rows,
        )


def _engine_metrics(
    engine: str,
    *,
    raw_results: list[dict],
    after_filter_companies: list[dict],
    final_companies: list[dict],
    profiled_domains: set[str],
) -> dict:
    engine_companies = [company for company in final_companies if engine in _company_engines(company)]
    domains = {company.get("domain", "") for company in engine_companies if company.get("domain", "")}
    profiled = domains & profiled_domains
    send_cv_count = sum(1 for company in engine_companies if company.get("next_action") == "Send CV")

    return {
        "raw_results": sum(1 for result in raw_results if _result_engine(result) == engine),
        "after_filter_companies": sum(
            1 for company in after_filter_companies if engine in _company_engines(company)
        ),
        "unique_companies": len(domains),
        "profiled_companies": len(profiled),
        "good_matches": sum(1 for company in engine_companies if company.get("qualification") == "Good Match"),
        "excellent_matches": sum(
            1 for company in engine_companies if company.get("qualification") == "Excellent Match"
        ),
        "send_cv_count": send_cv_count,
        "ignored_count": sum(1 for company in engine_companies if company.get("next_action") == "Ignore"),
        "precision": _rate(send_cv_count, len(domains)),
    }


def _company_engines(company: dict) -> list[str]:
    engines = company.get("engines") or [company.get("search_engine") or company.get("source", "")]
    return sorted({str(engine) for engine in engines if engine})


def _result_engine(result: dict) -> str:
    return str(result.get("source", "") or result.get("search_engine", "") or result.get("engine", ""))


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0
    return round(numerator / denominator, 4)


def _percent(value: object) -> str:
    return f"{float(value or 0) * 100:.1f}%"
