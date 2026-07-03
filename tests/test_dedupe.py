from src.dedupe import dedupe_companies


def test_dedupe_companies_by_domain() -> None:
    companies = [
        {"company": "A", "url": "https://example.com/?utm_source=x"},
        {"company": "A duplicate", "url": "https://www.example.com/about"},
    ]

    assert dedupe_companies(companies) == [
        {
            "company": "A",
            "url": "https://example.com/",
            "domain": "example.com",
            "discovery_confidence": 0,
        }
    ]


def test_dedupe_preserves_multiple_strategy_attribution() -> None:
    companies = [
        {
            "company": "A",
            "url": "https://a.it",
            "domain": "a.it",
            "queries": ["data entry Napoli contatti"],
            "engines": ["duckduckgo"],
            "strategies": ["career_search"],
            "discovery_confidence": 70,
        },
        {
            "company": "A",
            "url": "https://www.a.it/lavora-con-noi",
            "domain": "a.it",
            "queries": ["back office Campania lavora con noi"],
            "engines": ["duckduckgo"],
            "strategies": ["company_website_search"],
            "discovery_confidence": 90,
        },
    ]

    deduped = dedupe_companies(companies)

    assert deduped[0]["queries"] == [
        "back office Campania lavora con noi",
        "data entry Napoli contatti",
    ]
    assert deduped[0]["strategies"] == ["career_search", "company_website_search"]
    assert deduped[0]["engines"] == ["duckduckgo"]
    assert deduped[0]["original_query"] == "back office Campania lavora con noi"
    assert deduped[0]["discovery_strategy"] == "career_search"
    assert deduped[0]["search_engine"] == "duckduckgo"
