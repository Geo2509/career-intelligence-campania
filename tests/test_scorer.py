from src.scorer import score_company


def test_score_company_prefers_direct_contacts() -> None:
    scored = score_company(
        {
            "company": "Data Back Office Napoli",
            "url": "https://example.com",
            "emails": ["hr@example.com"],
            "phones": ["081123456"],
            "is_employer": True,
            "has_contact_page": True,
            "has_careers_page": True,
        }
    )

    assert scored["score"] > 0
    assert scored["confidence"] >= 90
    assert "Email found" in scored["positive_reasons"]
    assert scored["next_action"] == "Email direct contact"
