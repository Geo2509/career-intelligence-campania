from src.query_generator import DiscoveryQuery
from src.search.base import SearchStats
from src.strategy_performance import build_strategy_ranking, build_strategy_performance_report, print_strategy_report


def test_strategy_performance_calculation() -> None:
    stats = SearchStats(
        queries_by_strategy={"career_search": 2, "business_search": 1},
        cache_hits_by_strategy={"career_search": 1},
        cache_misses_by_strategy={"career_search": 1, "business_search": 1},
    )
    raw_results = [
        {"strategy": "career_search", "url": "https://a.it", "query": "career"},
        {"strategy": "career_search", "url": "https://b.it", "query": "career"},
        {"strategy": "business_search", "url": "https://c.it", "query": "business"},
    ]
    after_filter = [
        {"domain": "a.it", "strategies": ["career_search"]},
        {"domain": "b.it", "strategies": ["career_search"]},
        {"domain": "c.it", "strategies": ["business_search"]},
    ]
    final_companies = [
        {
            "domain": "a.it",
            "strategies": ["career_search"],
            "qualification": "Good Match",
            "next_action": "Send CV",
            "discovery_confidence": 80,
        },
        {
            "domain": "b.it",
            "strategies": ["career_search"],
            "qualification": "Excellent Match",
            "next_action": "Manual Review",
            "discovery_confidence": 60,
        },
        {
            "domain": "c.it",
            "strategies": ["business_search"],
            "qualification": "Not Relevant",
            "next_action": "Ignore",
            "discovery_confidence": 20,
        },
    ]

    report = build_strategy_performance_report(
        all_queries=[
            DiscoveryQuery("career", "career_search"),
            DiscoveryQuery("career contacts", "career_search"),
            DiscoveryQuery("business", "business_search"),
        ],
        search_stats=stats,
        raw_results=raw_results,
        after_filter_companies=after_filter,
        final_companies=final_companies,
        profiled_domains={"a.it", "b.it", "c.it"},
    )

    career = report["strategies"]["career_search"]
    assert career["queries_generated"] == 2
    assert career["queries_executed"] == 1
    assert career["cache_hits"] == 1
    assert career["raw_results"] == 2
    assert career["after_filter_companies"] == 2
    assert career["unique_domains"] == 2
    assert career["profiled_companies"] == 2
    assert career["good_matches"] == 1
    assert career["excellent_matches"] == 1
    assert career["send_cv_count"] == 1
    assert career["average_discovery_confidence"] == 70
    assert career["precision"] == 0.5
    assert report["best_strategy_by_send_cv"] == "career_search"
    assert report["strategies_with_only_ignored_companies"] == ["business_search"]


def test_precision_zero_division_safe() -> None:
    report = build_strategy_performance_report(
        all_queries=[DiscoveryQuery("unused", "unused_search")],
        search_stats=SearchStats(queries_by_strategy={"unused_search": 1}),
        raw_results=[],
        after_filter_companies=[],
        final_companies=[],
        profiled_domains=set(),
    )

    assert report["strategies"]["unused_search"]["profiled_companies"] == 0
    assert report["strategies"]["unused_search"]["precision"] == 0
    assert report["strategies_with_zero_results"] == ["unused_search"]


def test_multiple_strategy_attribution_in_report() -> None:
    report = build_strategy_performance_report(
        all_queries=[
            DiscoveryQuery("career", "career_search"),
            DiscoveryQuery("business", "business_search"),
        ],
        search_stats=SearchStats(
            queries_by_strategy={"career_search": 1, "business_search": 1},
            cache_misses_by_strategy={"career_search": 1, "business_search": 1},
        ),
        raw_results=[
            {"strategy": "career_search", "url": "https://a.it", "query": "career"},
            {"strategy": "business_search", "url": "https://a.it", "query": "business"},
        ],
        after_filter_companies=[{"domain": "a.it", "strategies": ["career_search", "business_search"]}],
        final_companies=[
            {
                "domain": "a.it",
                "strategies": ["career_search", "business_search"],
                "qualification": "Good Match",
                "next_action": "Send CV",
                "discovery_confidence": 75,
            }
        ],
        profiled_domains={"a.it"},
    )

    assert report["strategies"]["career_search"]["send_cv_count"] == 1
    assert report["strategies"]["business_search"]["send_cv_count"] == 1
    assert report["strategies"]["career_search"]["precision"] == 1
    assert report["strategies"]["business_search"]["precision"] == 1


def test_print_strategy_report_outputs_readable_table(capsys) -> None:
    print_strategy_report(
        {
            "strategies": {
                "career_search": {
                    "queries_executed": 3,
                    "raw_results": 10,
                    "unique_domains": 4,
                    "profiled_companies": 2,
                    "good_matches": 1,
                    "send_cv_count": 1,
                    "precision": 0.5,
                }
            }
        }
    )

    output = capsys.readouterr().out
    assert "Strategy" in output
    assert "Queries" in output
    assert "Send CV" in output
    assert "career_search" in output
    assert "0.50" in output


def test_strategy_ranking_scores_best_strategy_first() -> None:
    ranking = build_strategy_ranking(
        {
            "strategies": {
                "weak": {
                    "precision": 0,
                    "send_cv_count": 0,
                    "good_matches": 0,
                    "excellent_matches": 0,
                    "unique_domains": 5,
                    "raw_results": 20,
                },
                "strong": {
                    "precision": 0.75,
                    "send_cv_count": 3,
                    "good_matches": 2,
                    "excellent_matches": 1,
                    "unique_domains": 4,
                    "raw_results": 5,
                },
            }
        }
    )

    assert ranking["ranking"][0]["strategy"] == "strong"
    assert ranking["ranking"][0]["send_cv_rate"] == 0.75
    assert ranking["ranking"][0]["good_match_rate"] == 0.75
    assert ranking["ranking"][0]["strategy_score"] > ranking["ranking"][1]["strategy_score"]


def test_strategy_ranking_zero_result_strategy_scores_zero() -> None:
    ranking = build_strategy_ranking(
        {
            "strategies": {
                "empty": {
                    "precision": 0,
                    "send_cv_count": 0,
                    "good_matches": 0,
                    "excellent_matches": 0,
                    "unique_domains": 0,
                    "raw_results": 0,
                }
            }
        }
    )

    assert ranking["ranking"][0]["strategy_score"] == 0
