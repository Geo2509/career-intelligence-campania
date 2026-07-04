from pathlib import Path

from src.dedupe import dedupe_companies
from src.engine_performance import build_engine_performance_report, print_engine_report
from src.query_generator import DiscoveryQuery
from src.search.base import SearchResult, SearchStats
from src.search.cache import SearchCache
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
    monkeypatch.chdir(tmp_path)
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config, engine="serpapi")

    assert [client.name for client, _ in clients] == ["duckduckgo"]


def test_serpapi_missing_api_key_warns_before_duckduckgo_fallback(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    config = _search_config(tmp_path / "search_engines.yaml")

    load_search_clients(config, engine="serpapi")

    assert "Warning: SERPAPI_API_KEY is not set" in capsys.readouterr().err


def test_serpapi_selected_when_api_key_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config, engine="serpapi")

    assert [client.name for client, _ in clients] == ["serpapi"]


def test_serpapi_api_key_is_loaded_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SERPAPI_API_KEY=test-key\n")
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config, engine="serpapi")

    assert [client.name for client, _ in clients] == ["serpapi"]
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)


def test_all_engines_skips_serpapi_without_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config, engine="all")

    assert [client.name for client, _ in clients] == ["duckduckgo"]


def test_all_engines_uses_duckduckgo_and_serpapi_when_key_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    config = _search_config(tmp_path / "search_engines.yaml")

    clients = load_search_clients(config, engine="all")

    assert [client.name for client, _ in clients] == ["duckduckgo", "serpapi"]


def test_search_manager_uses_only_requested_duckduckgo_engine() -> None:
    duckduckgo = RecordingClient("duckduckgo")
    serpapi = RecordingClient("serpapi")

    run = SearchManager([(duckduckgo, 10)], cache=None).run(["data entry Napoli"])

    assert duckduckgo.calls == ["data entry Napoli"]
    assert serpapi.calls == []
    assert run.stats.ddg_results == 1
    assert run.stats.serpapi_results == 0


def test_search_manager_uses_only_requested_serpapi_engine() -> None:
    duckduckgo = RecordingClient("duckduckgo")
    serpapi = RecordingClient("serpapi")
    progress: list[str] = []

    run = SearchManager([(serpapi, 10)], cache=None).run(["data entry Napoli"], progress=progress.append)

    assert duckduckgo.calls == []
    assert serpapi.calls == ["data entry Napoli"]
    assert run.stats.ddg_results == 0
    assert run.stats.serpapi_results == 1
    assert any("SerpAPI: 1 results" in line for line in progress)
    assert not any("DDG:" in line for line in progress)


def test_search_manager_uses_both_engines_for_all_selection() -> None:
    duckduckgo = RecordingClient("duckduckgo")
    serpapi = RecordingClient("serpapi")

    run = SearchManager([(duckduckgo, 10), (serpapi, 10)], cache=None).run(["data entry Napoli"])

    assert duckduckgo.calls == ["data entry Napoli"]
    assert serpapi.calls == ["data entry Napoli"]
    assert run.stats.ddg_results == 1
    assert run.stats.serpapi_results == 1
    assert run.stats.queries_executed == 2


def test_duckduckgo_cache_is_not_reused_for_serpapi_run(tmp_path: Path) -> None:
    cache = SearchCache(tmp_path / "search_results.json", enabled=True, discovery_hash="hash")
    cache.set(
        "data entry Napoli",
        "duckduckgo",
        [
            SearchResult(
                query="data entry Napoli",
                title="DDG result",
                url="https://ddg.example",
                source="duckduckgo",
                strategy="direct",
            )
        ],
        strategy="direct",
    )
    serpapi = RecordingClient("serpapi")

    run = SearchManager([(serpapi, 10)], cache=cache).run(
        [DiscoveryQuery(query="data entry Napoli", strategy="direct")]
    )

    assert serpapi.calls == ["data entry Napoli"]
    assert run.stats.cache_hits == 0
    assert run.stats.serpapi_results == 1
    assert run.results[0].source == "serpapi"


class RecordingClient:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[str] = []
        self.last_error = ""

    def search(self, query: str, max_results: int = 10):
        self.calls.append(query)
        return [
            SearchResult(
                query=query,
                title=f"{self.name} result",
                url=f"https://{self.name}.example",
                source=self.name,
            )
        ]


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
