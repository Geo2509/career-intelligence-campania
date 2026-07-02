from src.scorer import score_company


def test_score_company_prefers_direct_contacts() -> None:
    scored = score_company(
        {
            "company": "Data Back Office Napoli",
            "url": "https://example.com",
            "emails": ["hr@example.com"],
            "has_contact_page": True,
            "has_careers_page": True,
        }
    )

    assert scored["score"] == 100
    assert "direct_email" in scored["score_reasons"]
