from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .query_generator import DiscoveryQuery
from .search.base import SearchStats


STRATEGY_COLUMNS = [
    "Strategy",
    "Queries",
    "Raw",
    "Unique",
    "Profiled",
    "Good",
    "Send CV",
    "Precision",
]


def build_strategy_performance_report(
    *,
    all_queries: Iterable[DiscoveryQuery],
    search_stats: SearchStats,
    raw_results: list[dict],
    after_filter_companies: list[dict],
    final_companies: list[dict],
    profiled_domains: set[str] | None = None,
) -> dict:
    query_list = list(all_queries)
    generated_counts: dict[str, int] = {}
    for query in query_list:
        if query.strategy:
            generated_counts[query.strategy] = generated_counts.get(query.strategy, 0) + 1
    strategies = set(generated_counts)
    strategies.update(strategy for strategy in search_stats.queries_by_strategy if strategy)
    strategies.update(_strategies_from_results(raw_results))
    strategies.update(_strategies_from_companies(after_filter_companies))
    strategies.update(_strategies_from_companies(final_companies))

    profiled_domains = profiled_domains or set()
    by_strategy = {
        strategy: _empty_strategy_metrics(search_stats, strategy, generated_counts)
        for strategy in sorted(strategies)
    }

    for result in raw_results:
        strategy = result.get("strategy", "")
        if strategy:
            by_strategy.setdefault(strategy, _empty_strategy_metrics(search_stats, strategy, generated_counts))["raw_results"] += 1

    for company in after_filter_companies:
        for strategy in _company_strategies(company):
            by_strategy.setdefault(strategy, _empty_strategy_metrics(search_stats, strategy, generated_counts))[
                "after_filter_companies"
            ] += 1

    domains_by_strategy: dict[str, set[str]] = {strategy: set() for strategy in by_strategy}
    profiled_by_strategy: dict[str, set[str]] = {strategy: set() for strategy in by_strategy}
    confidence_by_strategy: dict[str, list[int]] = {strategy: [] for strategy in by_strategy}

    for company in final_companies:
        domain = company.get("domain", "")
        for strategy in _company_strategies(company):
            metrics = by_strategy.setdefault(strategy, _empty_strategy_metrics(search_stats, strategy, generated_counts))
            domains_by_strategy.setdefault(strategy, set())
            profiled_by_strategy.setdefault(strategy, set())
            confidence_by_strategy.setdefault(strategy, [])

            if domain:
                domains_by_strategy[strategy].add(domain)
            if domain and domain in profiled_domains:
                profiled_by_strategy[strategy].add(domain)
            if company.get("qualification") == "Good Match":
                metrics["good_matches"] += 1
            if company.get("qualification") == "Excellent Match":
                metrics["excellent_matches"] += 1
            if company.get("next_action") == "Send CV":
                metrics["send_cv_count"] += 1
            if company.get("next_action") == "Ignore":
                metrics["ignored_count"] += 1
            confidence_by_strategy[strategy].append(int(company.get("discovery_confidence", 0) or 0))

    for strategy, metrics in by_strategy.items():
        metrics["unique_domains"] = len(domains_by_strategy.get(strategy, set()))
        metrics["profiled_companies"] = len(profiled_by_strategy.get(strategy, set()))
        confidences = confidence_by_strategy.get(strategy, [])
        metrics["average_discovery_confidence"] = round(sum(confidences) / len(confidences), 2) if confidences else 0
        metrics["precision"] = (
            round(metrics["send_cv_count"] / metrics["profiled_companies"], 4)
            if metrics["profiled_companies"]
            else 0
        )

    return {
        "strategies": by_strategy,
        "best_strategy_by_precision": _best_strategy(by_strategy, "precision"),
        "best_strategy_by_send_cv": _best_strategy(by_strategy, "send_cv_count"),
        "worst_strategy_by_precision": _worst_strategy(by_strategy, "precision"),
        "strategies_with_zero_results": sorted(
            strategy for strategy, metrics in by_strategy.items() if metrics["raw_results"] == 0
        ),
        "strategies_with_only_ignored_companies": sorted(
            strategy
            for strategy, metrics in by_strategy.items()
            if metrics["unique_domains"] > 0 and metrics["ignored_count"] == metrics["unique_domains"]
        ),
    }


def write_strategy_performance_report(report: dict, path: str | Path = "output/strategy_performance.json") -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def build_strategy_ranking(strategy_report: dict) -> dict:
    ranked = []
    for strategy, metrics in strategy_report.get("strategies", {}).items():
        ranked.append(
            {
                "strategy": strategy,
                "precision": float(metrics.get("precision", 0) or 0),
                "send_cv_rate": _safe_rate(metrics.get("send_cv_count", 0), metrics.get("unique_domains", 0)),
                "good_match_rate": _safe_rate(
                    int(metrics.get("good_matches", 0) or 0) + int(metrics.get("excellent_matches", 0) or 0),
                    metrics.get("unique_domains", 0),
                ),
                "unique_company_rate": _safe_rate(metrics.get("unique_domains", 0), metrics.get("raw_results", 0)),
                "duplicate_rate": round(
                    1 - _safe_rate(metrics.get("unique_domains", 0), metrics.get("raw_results", 0)),
                    4,
                )
                if int(metrics.get("raw_results", 0) or 0)
                else 0,
                "queries_generated": int(metrics.get("queries_generated", 0) or 0),
                "queries_executed": int(metrics.get("queries_executed", 0) or 0),
                "raw_results": int(metrics.get("raw_results", 0) or 0),
                "unique_domains": int(metrics.get("unique_domains", 0) or 0),
                "profiled_companies": int(metrics.get("profiled_companies", 0) or 0),
                "send_cv_count": int(metrics.get("send_cv_count", 0) or 0),
            }
        )

    for item in ranked:
        duplicate_quality = 1 - float(item["duplicate_rate"]) if item["raw_results"] else 0
        item["strategy_score"] = round(
            float(item["precision"]) * 0.35
            + float(item["send_cv_rate"]) * 0.25
            + float(item["good_match_rate"]) * 0.2
            + float(item["unique_company_rate"]) * 0.15
            + duplicate_quality * 0.05,
            4,
        )

    ranked = sorted(
        ranked,
        key=lambda item: (
            item["strategy_score"],
            item["send_cv_count"],
            item["unique_domains"],
            item["strategy"],
        ),
        reverse=True,
    )
    return {
        "ranking": ranked,
        "top_strategy": ranked[0]["strategy"] if ranked else "",
        "worst_strategy": ranked[-1]["strategy"] if ranked else "",
    }


def print_strategy_report(report: dict) -> None:
    rows = []
    for strategy, metrics in sorted(report.get("strategies", {}).items()):
        rows.append(
            [
                strategy,
                str(metrics.get("queries_executed", 0)),
                str(metrics.get("raw_results", 0)),
                str(metrics.get("unique_domains", 0)),
                str(metrics.get("profiled_companies", 0)),
                str(metrics.get("good_matches", 0)),
                str(metrics.get("send_cv_count", 0)),
                f"{float(metrics.get('precision', 0)):.2f}",
            ]
        )
    print_table(STRATEGY_COLUMNS, rows)


def _empty_strategy_metrics(search_stats: SearchStats, strategy: str, generated_counts: dict[str, int]) -> dict:
    return {
        "queries_generated": generated_counts.get(strategy, search_stats.queries_by_strategy.get(strategy, 0)),
        "queries_executed": search_stats.cache_misses_by_strategy.get(strategy, 0),
        "cache_hits": search_stats.cache_hits_by_strategy.get(strategy, 0),
        "raw_results": 0,
        "after_filter_companies": 0,
        "unique_domains": 0,
        "profiled_companies": 0,
        "good_matches": 0,
        "excellent_matches": 0,
        "send_cv_count": 0,
        "ignored_count": 0,
        "average_discovery_confidence": 0,
        "precision": 0,
    }


def _company_strategies(company: dict) -> list[str]:
    strategies = company.get("strategies") or [company.get("discovery_strategy") or company.get("strategy", "")]
    return sorted({str(strategy) for strategy in strategies if strategy})


def _strategies_from_results(results: list[dict]) -> set[str]:
    return {str(result.get("strategy", "")) for result in results if result.get("strategy")}


def _strategies_from_companies(companies: list[dict]) -> set[str]:
    strategies: set[str] = set()
    for company in companies:
        strategies.update(_company_strategies(company))
    return strategies


def _best_strategy(metrics_by_strategy: dict[str, dict], metric_name: str) -> str:
    if not metrics_by_strategy:
        return ""
    return max(metrics_by_strategy, key=lambda strategy: (metrics_by_strategy[strategy][metric_name], strategy))


def _worst_strategy(metrics_by_strategy: dict[str, dict], metric_name: str) -> str:
    if not metrics_by_strategy:
        return ""
    return min(metrics_by_strategy, key=lambda strategy: (metrics_by_strategy[strategy][metric_name], strategy))


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows)) if rows else len(headers[index])
        for index in range(len(headers))
    ]
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _safe_rate(numerator: object, denominator: object) -> float:
    denominator_int = int(denominator or 0)
    if denominator_int == 0:
        return 0
    return round(int(numerator or 0) / denominator_int, 4)
