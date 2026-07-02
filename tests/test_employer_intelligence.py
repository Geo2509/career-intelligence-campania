from src.employer_intelligence import enrich_company


def test_employer_intelligence_qualifies_logistics_back_office_company() -> None:
    company = {
        "company": "Campania Freight",
        "domain": "campaniafreight.it",
        "website": "https://campaniafreight.it",
        "region": "Campania",
        "page_text": (
            "Spedizioni internazionali import export dogana documentazione "
            "back office Excel SAP lavora con noi hr@campaniafreight.it"
        ),
        "emails": ["hr@campaniafreight.it"],
        "has_careers_page": True,
        "career_url": "https://campaniafreight.it/lavora-con-noi",
    }

    enriched = enrich_company(company)

    assert enriched["industry"] in {"Freight Forwarding", "Import Export", "Logistics"}
    assert "Freight Forwarder" in enriched["business_type"]
    assert enriched["logistics_score"] > 0
    assert enriched["office_score"] > 0
    assert enriched["hr_email"] == "hr@campaniafreight.it"
    assert enriched["qualification"] in {"Excellent Match", "Good Match"}
    assert enriched["next_action"] == "Send CV"
