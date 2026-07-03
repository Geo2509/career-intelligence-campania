import json
from pathlib import Path

from src.discovery_optimization import (
    build_discovery_recommendations,
    build_query_performance_report,
    rank_queries_for_execution,
    update_discovery_learning,
)
from src.query_generator import DiscoveryQuery


def test_query_ranking_counts_results_and_outcomes() -> None:
    report = build_query_performance_report(
        all_queries=[
            DiscoveryQuery("career query", "career_search"),
            DiscoveryQuery("empty query", "career_search"),
        ],
        raw_results=[
            {"query": "career query", "strategy": "career_search"},
            {"query": "career query", "strategy": "career_search"},
        ],
        final_companies=[
            {
                "domain": "a.it",
                "queries": ["career query"],
                "qualification": "Good Match",
                "next_action": "Send CV",
            },
            {
                "domain": "b.it",
                "queries": ["career query"],
                "qualification": "Possible Match",
                "next_action": "Manual Review",
            },
        ],
        profiled_domains={"a.it"},
    )

    metrics = report["queries"]["career query"]
    assert metrics["raw_results"] == 2
    assert metrics["unique_companies"] == 2
    assert metrics["profiled_companies"] == 1
    assert metrics["good_matches"] == 1
    assert metrics["send_cv_count"] == 1
    assert report["ranking"][0]["query"] == "career query"
    assert report["queries"]["empty query"]["query_score"] == 0


def test_adaptive_ordering_uses_historical_query_and_strategy_scores(tmp_path: Path) -> None:
    learning_path = tmp_path / "learning.json"
    learning_path.write_text(
        json.dumps(
            {
                "runs": [],
                "strategy_rolling": {
                    "strong_strategy": {"strategy_score": 0.8},
                    "weak_strategy": {"strategy_score": 0.1},
                },
                "query_rolling": {
                    "specific winner": {"query_score": 0.9},
                },
            }
        )
    )
    queries = [
        DiscoveryQuery("generic", "weak_strategy"),
        DiscoveryQuery("strategy winner", "strong_strategy"),
        DiscoveryQuery("specific winner", "weak_strategy"),
    ]

    ranked = rank_queries_for_execution(queries, learning_path)

    assert [query.query for query in ranked] == ["specific winner", "strategy winner", "generic"]


def test_recommendation_generation() -> None:
    recommendations = build_discovery_recommendations(
        strategy_ranking={
            "ranking": [
                {"strategy": "best", "strategy_score": 0.9},
                {"strategy": "middle", "strategy_score": 0.4},
                {"strategy": "worst", "strategy_score": 0.0},
            ]
        },
        query_performance={
            "ranking": [
                {
                    "query": "keep me",
                    "query_score": 0.8,
                    "raw_results": 4,
                    "unique_companies": 2,
                },
                {
                    "query": "rewrite me",
                    "query_score": 0.1,
                    "raw_results": 4,
                    "unique_companies": 0,
                },
                {
                    "query": "remove me",
                    "query_score": 0,
                    "raw_results": 0,
                    "unique_companies": 0,
                },
            ]
        },
        discovery_health={"unused_strategies": ["unused"]},
        strategy_performance={"strategies_with_only_ignored_companies": ["worst"]},
        learning={"query_rolling": {}},
    )

    assert recommendations["top_strategies"] == ["best", "middle", "worst"]
    assert recommendations["worst_strategies"][0] == "worst"
    assert "keep me" in recommendations["queries_to_keep"]
    assert recommendations["queries_to_remove"] == ["remove me"]
    assert recommendations["queries_to_rewrite"] == ["rewrite me"]
    assert recommendations["unused_strategies"] == ["unused"]
    assert recommendations["strategies_producing_only_ignored_companies"] == ["worst"]


def test_rolling_statistics_append_runs_and_average(tmp_path: Path) -> None:
    learning_path = tmp_path / "learning.json"

    update_discovery_learning(
        strategy_ranking={
            "ranking": [
                {
                    "strategy": "career",
                    "precision": 1,
                    "send_cv_rate": 1,
                    "good_match_rate": 1,
                    "unique_company_rate": 1,
                    "duplicate_rate": 0,
                    "strategy_score": 1,
                }
            ]
        },
        query_performance={
            "ranking": [
                {
                    "query": "career query",
                    "raw_results": 4,
                    "unique_companies": 2,
                    "profiled_companies": 1,
                    "good_matches": 1,
                    "send_cv_count": 1,
                    "query_score": 0.8,
                }
            ]
        },
        path=learning_path,
    )
    learning = update_discovery_learning(
        strategy_ranking={
            "ranking": [
                {
                    "strategy": "career",
                    "precision": 0,
                    "send_cv_rate": 0,
                    "good_match_rate": 0,
                    "unique_company_rate": 0,
                    "duplicate_rate": 1,
                    "strategy_score": 0,
                }
            ]
        },
        query_performance={
            "ranking": [
                {
                    "query": "career query",
                    "raw_results": 0,
                    "unique_companies": 0,
                    "profiled_companies": 0,
                    "good_matches": 0,
                    "send_cv_count": 0,
                    "query_score": 0,
                }
            ]
        },
        path=learning_path,
    )

    assert len(learning["runs"]) == 2
    assert learning["strategy_rolling"]["career"]["samples"] == 2
    assert learning["strategy_rolling"]["career"]["strategy_score"] == 0.5
    assert learning["query_rolling"]["career query"]["raw_results"] == 2
    assert learning["query_rolling"]["career query"]["query_score"] == 0.4
