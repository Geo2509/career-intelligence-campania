from src.dedupe import dedupe_companies


def test_dedupe_companies_by_domain() -> None:
    companies = [
        {"company": "A", "url": "https://example.com/?utm_source=x"},
        {"company": "A duplicate", "url": "https://www.example.com/about"},
    ]

    assert dedupe_companies(companies) == [
        {"company": "A", "url": "https://example.com/", "domain": "example.com"}
    ]
