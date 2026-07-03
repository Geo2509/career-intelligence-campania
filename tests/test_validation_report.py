from dataclasses import dataclass
from pathlib import Path

from src.validation import build_validation_report, print_validation_report


@dataclass
class FakeRunStats:
    after_aggregator_filter: int = 3
    profiled_companies: int = 2


def test_validation_report_counts_quality_region_industry_and_roles(tmp_path: Path) -> None:
    roles_path = tmp_path / "roles.yaml"
    locations_path = tmp_path / "locations.yaml"
    roles_path.write_text("roles:\n  - data entry\n  - back office\n")
    locations_path.write_text("locations:\n  - Napoli\n  - Pozzuoli\n")
    records = [
        {
            "domain": "a.it",
            "city": "Napoli",
            "industry": "Logistics",
            "qualification": "Good Match",
            "next_action": "Send CV",
            "queries": ["data entry Napoli contatti"],
            "title": "Data Entry Napoli",
        },
        {
            "domain": "b.it",
            "city": "Pozzuoli",
            "industry": "Shipping",
            "qualification": "Excellent Match",
            "next_action": "Manual Review",
            "queries": ["back office Pozzuoli"],
            "title": "Back Office Shipping",
        },
        {
            "domain": "c.it",
            "city": "",
            "industry": "",
            "qualification": "Possible Match",
            "next_action": "Ignore",
            "queries": ["remote document processing"],
            "snippet": "remote document processing",
        },
    ]

    report = build_validation_report(
        records=records,
        run_stats=FakeRunStats(),
        engine_performance={"engines": {"duckduckgo": {"queries": 2}}},
        strategy_ranking={"ranking": [{"strategy": "career_search", "strategy_score": 0.8}]},
        query_performance={"ranking": [{"query": "data entry Napoli contatti", "query_score": 0.9}]},
        discovery_recommendations={
            "queries_to_keep": ["data entry Napoli contatti"],
            "queries_to_remove": ["bad query"],
            "strategies_producing_only_ignored_companies": ["weak_strategy"],
        },
        roles_path=roles_path,
        locations_path=locations_path,
    )

    dataset = report["validation_dataset"]
    assert dataset["total_companies_discovered"] == 3
    assert dataset["unique_companies"] == 3
    assert dataset["profiled_companies"] == 2
    assert dataset["ignored_companies"] == 1
    assert dataset["possible_match"] == 1
    assert dataset["good_match"] == 1
    assert dataset["excellent_match"] == 1
    assert dataset["send_cv"] == 1
    assert dataset["manual_review"] == 1
    assert report["quality"]["precision"] == 0.5
    assert report["quality"]["send_cv_rate"] == 0.3333
    assert report["quality"]["good_match_rate"] == 0.6667
    assert report["quality"]["ignored_rate"] == 0.3333
    assert report["regional_analysis"]["Napoli"] == 1
    assert report["regional_analysis"]["Pozzuoli"] == 1
    assert report["regional_analysis"]["Remote"] == 1
    assert report["industry_analysis"]["Logistics"] == 1
    assert report["industry_analysis"]["Shipping"] == 1
    assert report["industry_analysis"]["Unknown"] == 1
    assert report["role_coverage"]["Data Entry"]["companies"] == 1
    assert report["role_coverage"]["Back Office"]["companies"] == 1
    assert report["engine_comparison"] == {"duckduckgo": {"queries": 2}}
    assert report["top_strategies"] == ["career_search"]
    assert report["top_queries"] == ["data entry Napoli contatti"]
    assert report["recommendations"]["queries_to_keep"] == ["data entry Napoli contatti"]
    assert report["recommendations"]["queries_to_remove"] == ["bad query"]
    assert "weak_strategy" in report["recommendations"]["strategies_to_disable"]
    assert "Salerno" in report["recommendations"]["cities_needing_more_coverage"]


def test_validation_report_prints_summary(capsys) -> None:
    print_validation_report(
        {
            "validation_dataset": {
                "unique_companies": 3,
                "profiled_companies": 2,
                "send_cv": 1,
                "manual_review": 1,
            },
            "quality": {
                "precision": 0.5,
                "good_match_rate": 0.6667,
                "ignored_rate": 0.3333,
            },
        }
    )

    output = capsys.readouterr().out
    assert "Unique Companies" in output
    assert "Precision" in output
    assert "0.50" in output
