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
                "positive_reasons": ["Logistics company"],
                "negative_reasons": [],
                "next_action": "Send CV",
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
        "Positive Reasons",
        "Negative Reasons",
        "Next Action",
    ):
        assert column in EXPORT_COLUMNS
        assert column in row
