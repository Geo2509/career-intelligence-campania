from src.scorer import score_companies, score_company


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
    assert scored["employer_priority_score"] >= 80
    assert scored["next_action"] == "Send CV"


def test_logistics_company_ranks_above_generic_it_services() -> None:
    ranked = score_companies(
        [
            {
                "company": "Generic IT Services",
                "domain": "generic-it.example",
                "website_type": "company",
                "industry": "IT",
                "page_text": "Servizi informatici consulenza software",
                "emails": ["info@generic-it.example"],
                "has_contact_page": True,
            },
            {
                "company": "Napoli Logistics",
                "domain": "napolilogistics.it",
                "website_type": "company",
                "industry": "Logistics",
                "business_type": ["B2B", "Freight Forwarder"],
                "company_size": "Medium",
                "city": "Napoli",
                "region": "Campania",
                "page_text": "Logistica supply chain import export back office lavora con noi posizioni aperte",
                "emails": ["hr@napolilogistics.it"],
                "hr_email": "hr@napolilogistics.it",
                "has_contact_page": True,
                "has_careers_page": True,
                "is_employer": True,
            },
        ]
    )

    assert ranked[0]["company"] == "Napoli Logistics"
    assert ranked[0]["employer_priority_score"] > ranked[1]["employer_priority_score"]


def test_direct_employer_ranks_above_staffing_agency() -> None:
    ranked = score_companies(
        [
            {
                "company": "Page Personnel",
                "domain": "pagepersonnel.it",
                "website_type": "staffing_agency",
                "page_text": "Agenzia per il lavoro recruitment offerte di lavoro candidati",
                "emails": ["info@pagepersonnel.it"],
                "has_careers_page": True,
            },
            {
                "company": "Direct Manufacturer",
                "domain": "manufacturer.it",
                "website_type": "company",
                "industry": "Manufacturing",
                "page_text": "Produzione document management back office contatti lavora con noi",
                "emails": ["hr@manufacturer.it"],
                "hr_email": "hr@manufacturer.it",
                "has_contact_page": True,
                "has_careers_page": True,
                "is_employer": True,
            },
        ]
    )

    assert ranked[0]["company"] == "Direct Manufacturer"
    assert ranked[1]["next_action"] != "Send CV"


def test_career_page_increases_priority() -> None:
    base = {
        "company": "Office Support",
        "domain": "office-support.it",
        "website_type": "company",
        "page_text": "Back office amministrazione data entry",
        "emails": ["info@office-support.it"],
        "has_contact_page": True,
        "is_employer": True,
    }

    without_career = score_company(base)
    with_career = score_company({**base, "has_careers_page": True, "career_url": "https://office-support.it/lavora"})

    assert with_career["employer_priority_score"] > without_career["employer_priority_score"]


def test_hr_email_increases_priority() -> None:
    base = {
        "company": "Office Company",
        "domain": "docs.it",
        "website_type": "company",
        "page_text": "Administrative services",
        "emails": ["info@docs.it"],
        "has_contact_page": True,
        "has_careers_page": True,
        "is_employer": True,
    }

    without_hr = score_company(base)
    with_hr = score_company({**base, "hr_email": "hr@docs.it"})

    assert with_hr["employer_priority_score"] > without_hr["employer_priority_score"]


def test_local_campania_employer_ranks_above_equivalent_outside_target_area() -> None:
    base = {
        "company": "Operations Employer",
        "domain": "operations.example",
        "website_type": "company",
        "industry": "Logistics",
        "page_text": "Supply chain operations",
        "emails": ["info@operations.example"],
        "has_contact_page": True,
        "is_employer": True,
    }

    outside = score_company({**base, "city": "Milano", "region": "Lombardia"})
    local = score_company({**base, "city": "Pozzuoli", "region": "Campania"})

    assert local["employer_priority_score"] > outside["employer_priority_score"]


def test_job_boards_never_receive_high_priority() -> None:
    scored = score_company(
        {
            "company": "I Programmatori",
            "domain": "iprogrammatori.it",
            "website_type": "job_board",
            "page_text": "Annunci lavoro offerte di lavoro candidati ora job alert",
            "emails": ["info@iprogrammatori.it"],
            "has_contact_page": True,
            "has_careers_page": True,
        }
    )

    assert scored["employer_priority_score"] < 80
    assert scored["next_action"] != "Send CV"
