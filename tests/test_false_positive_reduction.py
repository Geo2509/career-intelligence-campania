from src.company_extractor import extract_companies, load_excluded_domain_classes
from src.employer_intelligence import enrich_company
from src.intelligence.business_detector import detect_business
from src.intelligence.qualification import qualify_company


def test_known_job_boards_and_directories_are_excluded_by_extractor() -> None:
    results = [
        {"url": "https://jobijoba.it/offerte-lavoro/data-entry", "title": "Data entry", "source": "duckduckgo"},
        {"url": "https://jobsora.com/jobs-data-entry", "title": "Jobs", "source": "duckduckgo"},
        {"url": "https://europages.it/company/data-entry", "title": "Directory", "source": "duckduckgo"},
        {"url": "https://addlance.com/freelance/data-entry", "title": "Marketplace", "source": "duckduckgo"},
        {"url": "https://prontopro.it/na/data-entry", "title": "Marketplace", "source": "duckduckgo"},
    ]

    assert extract_companies(results, aggregators=list(load_excluded_domain_classes())) == []


def test_randstad_is_capped_as_staffing_agency() -> None:
    enriched = enrich_company(
        {
            "company": "Randstad",
            "domain": "randstad.it",
            "page_text": "Agenzia per il lavoro lavora con noi logistica back office",
            "career_url": "https://randstad.it/careers",
            "has_careers_page": True,
        }
    )

    assert enriched["qualification"] in {"Possible Match", "Low Match", "Not Relevant"}
    assert enriched["next_action"] == "Manual Review"
    assert "Excluded domain: staffing_agency" in enriched["negative_reasons"]


def test_portfolio_does_not_match_port_operator() -> None:
    result = detect_business({"domain": "agency.it", "page_text": "Portfolio clienti e carriera digitale"})

    assert "Port Operator" not in result["business_type"]
    assert "Carrier" not in result["business_type"]


def test_no_contact_path_caps_to_low_match() -> None:
    qualified = qualify_company(
        {
            "domain": "example.it",
            "industry": "Logistics",
            "business_type": ["Freight Forwarder"],
            "logistics_score": 80,
            "office_score": 80,
            "logistics_signals": ["Import", "Export", "Documentation"],
            "office_signals": ["Back Office", "Excel"],
            "region": "Campania",
        }
    )

    assert qualified["qualification"] == "Low Match"
    assert qualified["next_action"] == "Monitor Careers"
    assert "No contact path" in qualified["negative_reasons"]


def test_no_career_page_prevents_excellent_match() -> None:
    qualified = qualify_company(
        {
            "domain": "real-logistics.it",
            "industry": "Logistics",
            "business_type": ["Freight Forwarder", "B2B"],
            "logistics_score": 100,
            "office_score": 80,
            "logistics_signals": ["Import", "Export", "Documentation"],
            "office_signals": ["Back Office", "Excel"],
            "region": "Campania",
            "general_email": "info@real-logistics.it",
            "contact_url": "https://real-logistics.it/contatti",
            "is_employer": True,
        }
    )

    assert qualified["qualification"] != "Excellent Match"
    assert qualified["qualification"] == "Good Match"
