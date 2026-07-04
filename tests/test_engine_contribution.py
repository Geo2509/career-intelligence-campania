from src.dedupe import dedupe_companies
from src.engine_contribution import build_engine_contribution_report, print_engine_contribution_report


def test_engine_contribution_counts_only_and_shared_companies() -> None:
    report = build_engine_contribution_report(
        raw_results=[
            {"source": "duckduckgo", "url": "https://a.it"},
            {"source": "duckduckgo", "url": "https://shared.it"},
            {"source": "serpapi", "url": "https://b.it"},
            {"source": "serpapi", "url": "https://shared.it"},
        ],
        after_filter_companies=[
            _company("a.it", ["duckduckgo"]),
            _company("shared.it", ["duckduckgo"]),
            _company("b.it", ["serpapi"]),
            _company("shared.it", ["serpapi"]),
        ],
        final_companies=[
            _company("a.it", ["duckduckgo"], qualification="Good Match", next_action="Send CV"),
            _company("b.it", ["serpapi"], qualification="Excellent Match", next_action="Manual Review"),
            _company("shared.it", ["duckduckgo", "serpapi"], next_action="Ignore"),
        ],
        profiled_domains={"a.it", "shared.it"},
    )

    assert report["duckduckgo_only_companies"] == 1
    assert report["serpapi_only_companies"] == 1
    assert report["shared_companies"] == 1
    assert report["total_unique_companies"] == 3
    assert report["duckduckgo_unique_contribution_rate"] == 0.3333
    assert report["serpapi_unique_contribution_rate"] == 0.3333
    assert report["shared_rate"] == 0.3333
    assert report["engines"]["duckduckgo"]["raw_results"] == 2
    assert report["engines"]["duckduckgo"]["after_filter_companies"] == 2
    assert report["engines"]["duckduckgo"]["unique_companies"] == 2
    assert report["engines"]["duckduckgo"]["profiled_companies"] == 2
    assert report["engines"]["duckduckgo"]["good_matches"] == 1
    assert report["engines"]["duckduckgo"]["send_cv_count"] == 1
    assert report["engines"]["duckduckgo"]["ignored_count"] == 1
    assert report["engines"]["duckduckgo"]["precision"] == 0.5
    assert report["engines"]["serpapi"]["excellent_matches"] == 1


def test_engine_contribution_is_safe_when_one_engine_has_zero_results() -> None:
    report = build_engine_contribution_report(
        raw_results=[{"source": "duckduckgo", "url": "https://a.it"}],
        after_filter_companies=[_company("a.it", ["duckduckgo"])],
        final_companies=[_company("a.it", ["duckduckgo"])],
        profiled_domains=set(),
    )

    assert report["duckduckgo_only_companies"] == 1
    assert report["serpapi_only_companies"] == 0
    assert report["shared_companies"] == 0
    assert report["serpapi_unique_contribution_rate"] == 0
    assert report["shared_rate"] == 0
    assert report["engines"]["serpapi"]["raw_results"] == 0
    assert report["engines"]["serpapi"]["unique_companies"] == 0
    assert report["engines"]["serpapi"]["precision"] == 0


def test_engine_contribution_prints_compact_summary(capsys) -> None:
    report = build_engine_contribution_report(
        raw_results=[],
        after_filter_companies=[],
        final_companies=[
            _company("a.it", ["duckduckgo"]),
            _company("b.it", ["serpapi"]),
            _company("shared.it", ["duckduckgo", "serpapi"]),
        ],
        profiled_domains=set(),
    )

    print_engine_contribution_report(report)

    output = capsys.readouterr().out
    assert "Engine Contribution" in output
    assert "DuckDuckGo only: 1" in output
    assert "SerpAPI only: 1" in output
    assert "Shared: 1" in output
    assert "Total: 3" in output


def test_company_engine_attribution_marks_shared_companies() -> None:
    companies = dedupe_companies(
        [
            {
                "domain": "shared.it",
                "url": "https://shared.it",
                "engines": ["duckduckgo"],
                "queries": ["query one"],
                "strategies": ["direct"],
            },
            {
                "domain": "shared.it",
                "url": "https://www.shared.it/jobs",
                "engines": ["serpapi"],
                "queries": ["query two"],
                "strategies": ["career"],
            },
        ]
    )

    assert companies[0]["engines"] == ["duckduckgo", "serpapi"]
    assert companies[0]["queries"] == ["query one", "query two"]
    assert companies[0]["strategies"] == ["career", "direct"]


def _company(
    domain: str,
    engines: list[str],
    qualification: str = "",
    next_action: str = "",
) -> dict:
    return {
        "company": domain,
        "domain": domain,
        "url": f"https://{domain}",
        "engines": engines,
        "qualification": qualification,
        "next_action": next_action,
    }
