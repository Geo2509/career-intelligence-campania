from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .query_generator import DiscoveryQuery
from .strategy_performance import build_strategy_ranking, print_table


LEARNING_PATH = Path("output/discovery_learning.json")
QUERY_PERFORMANCE_PATH = Path("output/query_performance.json")
STRATEGY_RANKING_PATH = Path("output/strategy_ranking.json")
RECOMMENDATIONS_PATH = Path("output/discovery_recommendations.json")


def rank_queries_for_execution(
    queries: Iterable[DiscoveryQuery],
    learning_path: str | Path = LEARNING_PATH,
) -> list[DiscoveryQuery]:
    query_list = list(queries)
    learning = load_discovery_learning(learning_path)
    strategy_scores = {
        strategy: float(metrics.get("strategy_score", 0))
        for strategy, metrics in learning.get("strategy_rolling", {}).items()
    }
    query_scores = {
        query: float(metrics.get("query_score", 0))
        for query, metrics in learning.get("query_rolling", {}).items()
    }
    original_positions = {query: index for index, query in enumerate(query_list)}
    return sorted(
        query_list,
        key=lambda query: (
            query_scores.get(query.query, 0),
            strategy_scores.get(query.strategy, 0),
            -original_positions[query],
        ),
        reverse=True,
    )


def build_query_performance_report(
    *,
    all_queries: Iterable[DiscoveryQuery],
    raw_results: list[dict],
    final_companies: list[dict],
    profiled_domains: set[str] | None = None,
) -> dict:
    query_list = list(all_queries)
    profiled_domains = profiled_domains or set()
    query_metrics = {
        query.query: {
            "query": query.query,
            "strategy": query.strategy,
            "raw_results": 0,
            "unique_companies": 0,
            "profiled_companies": 0,
            "good_matches": 0,
            "send_cv_count": 0,
            "query_score": 0,
        }
        for query in query_list
    }
    raw_seen: set[str] = set(query_metrics)
    for result in raw_results:
        query = result.get("query", "")
        if not query:
            continue
        raw_seen.add(query)
        metrics = query_metrics.setdefault(query, _empty_query_metrics(query, result.get("strategy", "")))
        metrics["raw_results"] += 1

    domains_by_query: dict[str, set[str]] = {query: set() for query in query_metrics}
    profiled_by_query: dict[str, set[str]] = {query: set() for query in query_metrics}
    for company in final_companies:
        domain = company.get("domain", "")
        for query in _company_queries(company):
            raw_seen.add(query)
            metrics = query_metrics.setdefault(query, _empty_query_metrics(query, company.get("strategy", "")))
            domains_by_query.setdefault(query, set())
            profiled_by_query.setdefault(query, set())
            if domain:
                domains_by_query[query].add(domain)
            if domain and domain in profiled_domains:
                profiled_by_query[query].add(domain)
            if company.get("qualification") in {"Good Match", "Excellent Match"}:
                metrics["good_matches"] += 1
            if company.get("next_action") == "Send CV":
                metrics["send_cv_count"] += 1

    for query, metrics in query_metrics.items():
        metrics["unique_companies"] = len(domains_by_query.get(query, set()))
        metrics["profiled_companies"] = len(profiled_by_query.get(query, set()))
        metrics["query_score"] = calculate_query_score(metrics)

    ranked = sorted(
        query_metrics.values(),
        key=lambda metrics: (
            metrics["query_score"],
            metrics["send_cv_count"],
            metrics["good_matches"],
            metrics["unique_companies"],
            metrics["raw_results"],
            metrics["query"],
        ),
        reverse=True,
    )
    return {
        "generated_at": _utc_now(),
        "queries": {metrics["query"]: metrics for metrics in ranked},
        "ranking": ranked,
    }


def calculate_query_score(metrics: dict) -> float:
    raw_results = int(metrics.get("raw_results", 0) or 0)
    unique_companies = int(metrics.get("unique_companies", 0) or 0)
    profiled_companies = int(metrics.get("profiled_companies", 0) or 0)
    good_matches = int(metrics.get("good_matches", 0) or 0)
    send_cv_count = int(metrics.get("send_cv_count", 0) or 0)
    unique_rate = unique_companies / raw_results if raw_results else 0
    profile_rate = profiled_companies / unique_companies if unique_companies else 0
    good_rate = good_matches / unique_companies if unique_companies else 0
    send_cv_rate = send_cv_count / unique_companies if unique_companies else 0
    return round(
        send_cv_rate * 0.4
        + good_rate * 0.25
        + unique_rate * 0.2
        + profile_rate * 0.1
        + min(raw_results, 20) / 20 * 0.05,
        4,
    )


def write_query_performance_report(report: dict, path: str | Path = QUERY_PERFORMANCE_PATH) -> None:
    _write_json(report, path)


def update_discovery_learning(
    *,
    strategy_ranking: dict,
    query_performance: dict,
    path: str | Path = LEARNING_PATH,
) -> dict:
    learning = load_discovery_learning(path)
    run_id = _utc_now()
    run_record = {
        "generated_at": run_id,
        "strategies": list(strategy_ranking.get("ranking", [])),
        "queries": list(query_performance.get("ranking", [])),
    }
    learning.setdefault("runs", []).append(run_record)
    learning["strategy_rolling"] = _update_rolling(
        learning.get("strategy_rolling", {}),
        strategy_ranking.get("ranking", []),
        key_field="strategy",
        metric_fields=(
            "precision",
            "send_cv_rate",
            "good_match_rate",
            "unique_company_rate",
            "duplicate_rate",
            "strategy_score",
        ),
    )
    learning["query_rolling"] = _update_rolling(
        learning.get("query_rolling", {}),
        query_performance.get("ranking", []),
        key_field="query",
        metric_fields=(
            "raw_results",
            "unique_companies",
            "profiled_companies",
            "good_matches",
            "send_cv_count",
            "query_score",
        ),
    )
    _write_json(learning, path)
    return learning


def build_discovery_recommendations(
    *,
    strategy_ranking: dict,
    query_performance: dict,
    discovery_health: dict,
    strategy_performance: dict,
    learning: dict | None = None,
) -> dict:
    strategies = strategy_ranking.get("ranking", [])
    queries = query_performance.get("ranking", [])
    query_rolling = (learning or {}).get("query_rolling", {})
    ranked_queries = _rank_queries_with_history(queries, query_rolling)
    return {
        "generated_at": _utc_now(),
        "top_strategies": [item["strategy"] for item in strategies[:3]],
        "worst_strategies": [item["strategy"] for item in list(reversed(strategies[-3:]))],
        "queries_to_keep": [item["query"] for item in ranked_queries[:10] if _historical_query_score(item, query_rolling) > 0],
        "queries_to_remove": [
            item["query"]
            for item in ranked_queries
            if int(item.get("raw_results", 0) or 0) == 0 and _historical_query_score(item, query_rolling) == 0
        ][:20],
        "queries_to_rewrite": [
            item["query"]
            for item in ranked_queries
            if int(item.get("raw_results", 0) or 0) > 0
            and int(item.get("unique_companies", 0) or 0) == 0
            and _historical_query_score(item, query_rolling) < 0.2
        ][:20],
        "unused_strategies": discovery_health.get("unused_strategies", []),
        "strategies_producing_only_ignored_companies": strategy_performance.get(
            "strategies_with_only_ignored_companies", []
        ),
    }


def build_historical_strategy_ranking(learning: dict, fallback_ranking: dict | None = None) -> dict:
    rolling = learning.get("strategy_rolling", {})
    if not rolling:
        return fallback_ranking or {"ranking": [], "top_strategy": "", "worst_strategy": ""}
    ranked = []
    for strategy, metrics in rolling.items():
        ranked.append(
            {
                "strategy": strategy,
                "samples": int(metrics.get("samples", 0) or 0),
                "precision": float(metrics.get("precision", 0) or 0),
                "send_cv_rate": float(metrics.get("send_cv_rate", 0) or 0),
                "good_match_rate": float(metrics.get("good_match_rate", 0) or 0),
                "unique_company_rate": float(metrics.get("unique_company_rate", 0) or 0),
                "duplicate_rate": float(metrics.get("duplicate_rate", 0) or 0),
                "strategy_score": float(metrics.get("strategy_score", 0) or 0),
                "last_seen_at": metrics.get("last_seen_at", ""),
            }
        )
    ranked = sorted(
        ranked,
        key=lambda item: (item["strategy_score"], item["samples"], item["strategy"]),
        reverse=True,
    )
    return {
        "generated_at": _utc_now(),
        "basis": "rolling_averages",
        "ranking": ranked,
        "top_strategy": ranked[0]["strategy"] if ranked else "",
        "worst_strategy": ranked[-1]["strategy"] if ranked else "",
    }


def write_discovery_recommendations(report: dict, path: str | Path = RECOMMENDATIONS_PATH) -> None:
    _write_json(report, path)


def print_strategy_ranking(report: dict) -> None:
    rows = [
        [
            item["strategy"],
            f"{float(item.get('strategy_score', 0)):.2f}",
            f"{float(item.get('precision', 0)):.2f}",
            f"{float(item.get('send_cv_rate', 0)):.2f}",
            f"{float(item.get('good_match_rate', 0)):.2f}",
            f"{float(item.get('unique_company_rate', 0)):.2f}",
        ]
        for item in report.get("ranking", [])
    ]
    print_table(["Strategy", "Score", "Precision", "Send CV", "Good", "Unique"], rows)


def print_query_ranking(report: dict, limit: int = 25) -> None:
    rows = [
        [
            item["query"],
            item.get("strategy", ""),
            str(item.get("raw_results", 0)),
            str(item.get("unique_companies", 0)),
            str(item.get("profiled_companies", 0)),
            str(item.get("good_matches", 0)),
            str(item.get("send_cv_count", 0)),
            f"{float(item.get('query_score', 0)):.2f}",
        ]
        for item in report.get("ranking", [])[:limit]
    ]
    print_table(["Query", "Strategy", "Raw", "Unique", "Profiled", "Good", "Send CV", "Score"], rows)


def print_recommendations(report: dict) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2))


def load_discovery_learning(path: str | Path = LEARNING_PATH) -> dict:
    learning_path = Path(path)
    if not learning_path.exists():
        return {"runs": [], "strategy_rolling": {}, "query_rolling": {}}
    try:
        return json.loads(learning_path.read_text())
    except json.JSONDecodeError:
        return {"runs": [], "strategy_rolling": {}, "query_rolling": {}}


def _empty_query_metrics(query: str, strategy: str) -> dict:
    return {
        "query": query,
        "strategy": strategy,
        "raw_results": 0,
        "unique_companies": 0,
        "profiled_companies": 0,
        "good_matches": 0,
        "send_cv_count": 0,
        "query_score": 0,
    }


def _company_queries(company: dict) -> list[str]:
    queries = company.get("queries") or [company.get("original_query") or company.get("query", "")]
    return sorted({str(query) for query in queries if query})


def _update_rolling(
    existing: dict,
    current_items: list[dict],
    *,
    key_field: str,
    metric_fields: tuple[str, ...],
) -> dict:
    updated = {key: dict(value) for key, value in existing.items()}
    for item in current_items:
        key = item.get(key_field, "")
        if not key:
            continue
        current = updated.setdefault(key, {"samples": 0})
        samples = int(current.get("samples", 0))
        next_samples = samples + 1
        for field in metric_fields:
            previous = float(current.get(field, 0) or 0)
            value = float(item.get(field, 0) or 0)
            current[field] = round(((previous * samples) + value) / next_samples, 4)
        current["samples"] = next_samples
        current["last_seen_at"] = _utc_now()
    return updated


def _rank_queries_with_history(queries: list[dict], query_rolling: dict) -> list[dict]:
    return sorted(
        queries,
        key=lambda item: (
            _historical_query_score(item, query_rolling),
            item.get("send_cv_count", 0),
            item.get("good_matches", 0),
            item.get("unique_companies", 0),
            item.get("query", ""),
        ),
        reverse=True,
    )


def _historical_query_score(item: dict, query_rolling: dict) -> float:
    historical = query_rolling.get(item.get("query", ""), {})
    if historical:
        return float(historical.get("query_score", 0) or 0)
    return float(item.get("query_score", 0) or 0)


def _write_json(data: dict, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
