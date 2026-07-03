from __future__ import annotations

import json
from pathlib import Path

from .search.base import SearchStats
from .strategy_performance import print_table


ENGINE_PERFORMANCE_PATH = Path("output/engine_performance.json")


def build_engine_performance_report(
    *,
    search_stats: SearchStats,
    raw_results: list[dict],
    final_companies: list[dict],
) -> dict:
    engines = set(search_stats.queries_by_engine)
    engines.update(result.get("source", "") or result.get("engine", "") for result in raw_results)
    engines.update(_engines_from_companies(final_companies))
    engines.discard("")

    report = {
        engine: {
            "queries": int(search_stats.queries_by_engine.get(engine, 0) or 0),
            "results": 0,
            "unique_companies": 0,
            "good_matches": 0,
            "send_cv_count": 0,
            "duplicates": 0,
            "precision": 0,
            "average_confidence": 0,
        }
        for engine in sorted(engines)
    }

    for result in raw_results:
        engine = result.get("source", "") or result.get("engine", "")
        if not engine:
            continue
        metrics = report.setdefault(engine, _empty_engine_metrics(search_stats, engine))
        metrics["results"] += 1

    domains_by_engine: dict[str, set[str]] = {engine: set() for engine in report}
    confidence_by_engine: dict[str, list[int]] = {engine: [] for engine in report}
    for company in final_companies:
        domain = company.get("domain", "")
        for engine in _company_engines(company):
            metrics = report.setdefault(engine, _empty_engine_metrics(search_stats, engine))
            domains_by_engine.setdefault(engine, set())
            confidence_by_engine.setdefault(engine, [])
            if domain:
                domains_by_engine[engine].add(domain)
            if company.get("qualification") in {"Good Match", "Excellent Match"}:
                metrics["good_matches"] += 1
            if company.get("next_action") == "Send CV":
                metrics["send_cv_count"] += 1
            confidence_by_engine[engine].append(int(company.get("confidence", 0) or 0))

    for engine, metrics in report.items():
        metrics["unique_companies"] = len(domains_by_engine.get(engine, set()))
        metrics["duplicates"] = max(0, int(metrics["results"]) - metrics["unique_companies"])
        metrics["precision"] = (
            round(metrics["send_cv_count"] / metrics["unique_companies"], 4)
            if metrics["unique_companies"]
            else 0
        )
        confidences = confidence_by_engine.get(engine, [])
        metrics["average_confidence"] = round(sum(confidences) / len(confidences), 2) if confidences else 0

    return {"engines": report}


def write_engine_performance_report(
    report: dict,
    path: str | Path = ENGINE_PERFORMANCE_PATH,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def print_engine_report(report: dict) -> None:
    rows = []
    for engine, metrics in sorted(report.get("engines", {}).items()):
        rows.append(
            [
                engine,
                str(metrics.get("queries", 0)),
                str(metrics.get("results", 0)),
                str(metrics.get("unique_companies", 0)),
                str(metrics.get("good_matches", 0)),
                str(metrics.get("send_cv_count", 0)),
                f"{float(metrics.get('precision', 0)):.2f}",
            ]
        )
    print_table(
        ["Engine", "Queries", "Results", "Unique Companies", "Good Matches", "Send CV", "Precision"],
        rows,
    )


def _empty_engine_metrics(search_stats: SearchStats, engine: str) -> dict:
    return {
        "queries": int(search_stats.queries_by_engine.get(engine, 0) or 0),
        "results": 0,
        "unique_companies": 0,
        "good_matches": 0,
        "send_cv_count": 0,
        "duplicates": 0,
        "precision": 0,
        "average_confidence": 0,
    }


def _company_engines(company: dict) -> list[str]:
    engines = company.get("engines") or [company.get("search_engine") or company.get("source", "")]
    return sorted({str(engine) for engine in engines if engine})


def _engines_from_companies(companies: list[dict]) -> set[str]:
    engines: set[str] = set()
    for company in companies:
        engines.update(_company_engines(company))
    return engines
