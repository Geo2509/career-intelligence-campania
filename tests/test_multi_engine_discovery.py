from pathlib import Path

from src.dedupe import dedupe_companies
from src.engine_performance import build_engine_performance_report, print_engine_report
from src.search.base import SearchResult, SearchStats
from src.search.search_manager import SearchManager, load_search_clients


def _search_config(path: Path, duckduckgo_enabled: bool = True) -> Path:
    path.write_text(
        "engines:\n"
        "  duckduckgo:\n"
        f"    enabled: {str(duckduckgo_enabled).lower()}\n"
        "    max_results: 5\n"
        "  serpapi:\n"
        "    enabled: false\n"
        "    max_results: 5\n"
        "    api_key_env: SERPAPI_API_KEY\n"
        "cache:\n"
        "  enabled: false\n"
    )
    return path


def test_engine_selection_defaults_to_duckduckgo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config)

    assert [client.name for client, _ in clients] == ["duckduckgo"]


def test_serpapi_missing_api_key_falls_back_to_duckduckgo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config, engine="serpapi")

    assert [client.name for client, _ in clients] == ["duckduckgo"]


def test_serpapi_selected_when_api_key_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config, engine="serpapi")

    assert [client.name for client, _ in clients] == ["serpapi"]


def test_all_engines_skips_serpapi_without_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config, engine="all")

    assert [client.name for client, _ in clients] == ["duckduckgo"]


def test_search_manager_records_engine_statistics() -> None:
    class FakeClient:
        name = "fake"

        def search(self, query: str, max_results: int = 10):
            return [
                SearchResult(
                    query=query,
                    title="A",
                    url="https://a.it",
                    source=self.name,
                )
            ]

    run = SearchManager([(FakeClient(), 10)], cache=None).run(["data entry Napoli"])

    assert run.stats.queries_by_engine == {"fake": 1}
    assert run.stats.results_by_engine == {"fake": 1}
    assert run.results[0].source == "fake"


def test_cross_engine_deduplication_preserves_all_engines_queries_and_strategies() -> None:
    deduped = dedupe_companies(
        [
            {
                "company": "A",
                "domain": "a.it",
                "url": "https://a.it",
                "engines": ["duckduckgo"],
                "queries": ["query one"],
                "strategies": ["career_search"],
                "discovery_confidence": 70,
            },
            {
                "company": "A",
                "domain": "a.it",
                "url": "https://www.a.it/jobs",
                "engines": ["serpapi"],
                "queries": ["query two"],
                "strategies": ["company_website_search"],
                "discovery_confidence": 80,
            },
        ]
    )

    assert len(deduped) == 1
    assert deduped[0]["engines"] == ["duckduckgo", "serpapi"]
    assert deduped[0]["queries"] == ["query one", "query two"]
    assert deduped[0]["strategies"] == ["career_search", "company_website_search"]


def test_engine_performance_report_calculates_metrics() -> None:
    stats = SearchStats(queries_by_engine={"duckduckgo": 2, "serpapi": 2})
    raw_results = [
        {"source": "duckduckgo", "url": "https://a.it"},
        {"source": "duckduckgo", "url": "https://a.it/jobs"},
        {"source": "serpapi", "url": "https://b.it"},
    ]
    companies = [
        {
            "domain": "a.it",
            "engines": ["duckduckgo"],
            "qualification": "Good Match",
            "next_action": "Send CV",
            "confidence": 80,
        },
        {
            "domain": "b.it",
            "engines": ["serpapi"],
            "qualification": "Possible Match",
            "next_action": "Manual Review",
            "confidence": 40,
        },
    ]

    report = build_engine_performance_report(
        search_stats=stats,
        raw_results=raw_results,
        final_companies=companies,
    )

    assert report["engines"]["duckduckgo"]["queries"] == 2
    assert report["engines"]["duckduckgo"]["results"] == 2
    assert report["engines"]["duckduckgo"]["unique_companies"] == 1
    assert report["engines"]["duckduckgo"]["good_matches"] == 1
    assert report["engines"]["duckduckgo"]["send_cv_count"] == 1
    assert report["engines"]["duckduckgo"]["duplicates"] == 1
    assert report["engines"]["duckduckgo"]["precision"] == 1
    assert report["engines"]["duckduckgo"]["average_confidence"] == 80


def test_print_engine_report_outputs_readable_table(capsys) -> None:
    print_engine_report(
        {
            "engines": {
                "duckduckgo": {
                    "queries": 2,
                    "results": 4,
                    "unique_companies": 3,
                    "good_matches": 1,
                    "send_cv_count": 1,
                    "precision": 0.3333,
                }
            }
        }
    )

    output = capsys.readouterr().out
    assert "Engine" in output
    assert "Unique Companies" in output
    assert "duckduckgo" in output
    assert "0.33" in output
