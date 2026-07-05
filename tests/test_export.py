from src.export import EXPORT_COLUMNS, records_to_export_rows


def test_export_contains_milestone_2_columns() -> None:
    row = records_to_export_rows(
        [
            {
                "company": "A",
                "domain": "a.it",
                "industry": "Logistics",
                "business_type": ["B2B", "Freight Forwarder"],
                "company_size": "Medium",
                "logistics_score": 40,
                "office_score": 24,
                "career_page": "https://a.it/careers",
                "hr_email": "hr@a.it",
                "linkedin": "https://linkedin.com/company/a",
                "facebook": "https://facebook.com/a",
                "qualification": "Good Match",
                "employer_priority_score": 88,
                "employer_priority_reasons": ["+14 direct employer", "+10 career page"],
                "employer_priority_confidence": 92,
                "confidence": 65,
                "discovery_confidence": 80,
                "strategy": "career_search",
                "queries": ["data entry Napoli contatti"],
                "engines": ["duckduckgo"],
                "positive_reasons": ["Logistics company"],
                "negative_reasons": [],
                "next_action": "Send CV",
                "website_type_initial": "company",
                "website_type_initial_confidence": 65,
                "website_type": "staffing_agency",
                "website_type_confidence": 95,
                "website_type_final": "staffing_agency",
                "website_type_final_confidence": 95,
                "website_type_final_reasons": ["agenzia per il lavoro:45"],
            }
        ]
    )[0]

    for column in (
        "Industry",
        "Business Type",
        "Company Size",
        "Logistics Score",
        "Office Score",
        "Career Page",
        "HR Email",
        "LinkedIn",
        "Facebook",
        "Qualification",
        "Employer Priority Score",
        "Employer Priority Reasons",
        "Employer Priority Confidence",
        "Discovery Confidence",
        "Discovery Confidence Level",
        "Discovery Strategy",
        "Original Query",
        "Search Engine",
        "Positive Reasons",
        "Negative Reasons",
        "Next Action",
        "Website Type Initial",
        "Website Type Final",
        "Website Type Final Confidence",
        "Website Type Final Reasons",
    ):
        assert column in EXPORT_COLUMNS
        assert column in row

    assert row["Website Type"] == "staffing_agency"
    assert row["Website Type Confidence"] == 95
    assert row["Website Type Initial"] == "company"
    assert row["Website Type Final"] == "staffing_agency"
    assert row["Employer Priority Score"] == 88
    assert row["Employer Priority Confidence"] == 92
