from src.employer_intelligence import enrich_company


def test_ciesseservices_is_downgraded_to_possible_manual_review() -> None:
    enriched = enrich_company(
        {
            "company": "Data Entry per le aziende a Milano",
            "domain": "ciesseservices.it",
            "industry": "Logistics",
            "page_text": (
                "Traslochi Milano Monza Aziende Privati Depositi Spedizioni "
                "Servizi per l'ufficio Preventivi"
            ),
            "logistics_score": 50,
            "office_score": 24,
            "contact_url": "https://ciesseservices.it/contatti",
            "is_employer": True,
        }
    )

    assert enriched["qualification"] == "Possible Match"
    assert enriched["next_action"] == "Manual Review"
    assert "Weak geographic fit" in enriched["negative_reasons"]


def test_sistemiufficio_is_manual_review_without_strong_fit() -> None:
    enriched = enrich_company(
        {
            "company": "Sistemi Ufficio",
            "domain": "sistemiufficio.it",
            "page_text": "Soluzioni digitali e IT Noleggio operativo device Consulenza energetica",
            "emails": ["info@sistemiufficio.it"],
            "career_url": "https://sistemiufficio.it/lavora-con-noi/",
            "has_careers_page": True,
            "is_employer": True,
        }
    )

    assert enriched["qualification"] in {"Possible Match", "Good Match"}
    assert enriched["next_action"] == "Manual Review"
    assert "No strong logistics/back-office evidence" in enriched["negative_reasons"]


def test_aligned_document_service_without_career_can_send_cv() -> None:
    enriched = enrich_company(
        {
            "company": "Stasis",
            "domain": "stasis.it",
            "page_text": "Archiviazione ottica gestione documentale data entry documenti contatti",
            "emails": ["info@stasis.it"],
            "is_employer": True,
            "region": "Campania",
        }
    )

    assert enriched["qualification"] == "Good Match"
    assert enriched["next_action"] == "Send CV"


def test_gruppozenit_can_remain_good_with_career_page() -> None:
    enriched = enrich_company(
        {
            "company": "Gruppo Zenit",
            "domain": "gruppozenit.com",
            "page_text": "IT Managed Services Software Solutions Data Entry Excel Reporting CAREERS",
            "emails": ["info@zenit.it"],
            "career_url": "https://career.gruppozenit.com",
            "has_careers_page": True,
            "is_employer": True,
            "region": "Campania",
        }
    )

    assert enriched["qualification"] == "Good Match"
    assert enriched["next_action"] == "Send CV"


def test_email_alone_never_produces_send_cv() -> None:
    enriched = enrich_company(
        {
            "company": "Generic Services",
            "domain": "genericservices.it",
            "page_text": "Servizi informatici e consulenza",
            "emails": ["info@genericservices.it"],
            "is_employer": True,
        }
    )

    assert enriched["next_action"] == "Manual Review"
    assert "Email only" in enriched["negative_reasons"]


def test_weak_geographic_fit_blocks_send_cv_without_strong_reason() -> None:
    enriched = enrich_company(
        {
            "company": "Milano Services",
            "domain": "milanoservices.it",
            "page_text": "Milano Monza servizi software data entry",
            "emails": ["info@milanoservices.it"],
            "is_employer": True,
        }
    )

    assert enriched["next_action"] == "Manual Review"
    assert "Weak geographic fit" in enriched["negative_reasons"]


def test_career_page_can_override_with_moderate_office_fit() -> None:
    enriched = enrich_company(
        {
            "company": "Career Data",
            "domain": "careerdata.it",
            "page_text": "Data entry Excel reporting careers",
            "emails": ["info@careerdata.it"],
            "career_url": "https://careerdata.it/careers",
            "has_careers_page": True,
            "is_employer": True,
            "region": "Campania",
        }
    )

    assert enriched["qualification"] in {"Good Match", "Excellent Match"}
    assert enriched["next_action"] == "Send CV"


def test_inputdata_style_email_only_it_service_is_manual_review() -> None:
    enriched = enrich_company(
        {
            "company": "Input Data",
            "domain": "inputdata.it",
            "page_text": "Software e servizi informatici soluzioni a portata di mano contatti",
            "emails": ["amministrazione@inputsoft.it"],
            "is_employer": True,
            "region": "Campania",
        }
    )

    assert enriched["next_action"] == "Manual Review"
