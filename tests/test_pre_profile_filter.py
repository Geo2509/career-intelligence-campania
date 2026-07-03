from src.employer_intelligence import enrich_company
from src.main import select_companies_for_profiling, weak_employer_evidence


def test_excluded_domains_are_filtered_before_profiling() -> None:
    selected, skipped = select_companies_for_profiling(
        [
            {"domain": "jobatus.it", "title": "Data entry Napoli"},
            {"domain": "realazienda.it", "title": "Azienda logistica export"},
        ]
    )

    assert [company["domain"] for company in selected] == ["realazienda.it"]
    assert skipped["skipped_domain_excluded"] == 1
    assert skipped["skipped_job_board"] == 1


def test_public_sector_domains_are_not_profiled() -> None:
    selected, skipped = select_companies_for_profiling([{"domain": "senato.it", "title": "Ufficio"}])

    assert selected == []
    assert skipped["skipped_domain_excluded"] == 1
    assert skipped["skipped_public_sector"] == 1


def test_social_domains_are_not_profiled() -> None:
    selected, skipped = select_companies_for_profiling([{"domain": "instagram.com", "title": "Azienda"}])

    assert selected == []
    assert skipped["skipped_domain_excluded"] == 1
    assert skipped["skipped_social"] == 1


def test_max_profile_companies_limit_works() -> None:
    companies = [
        {"domain": "a.it", "title": "Azienda logistica"},
        {"domain": "b.it", "title": "Azienda export"},
        {"domain": "c.it", "title": "Azienda servizi"},
    ]

    selected, skipped = select_companies_for_profiling(companies, max_profile_companies=2)

    assert [company["domain"] for company in selected] == ["a.it", "b.it"]
    assert skipped["max_profile_companies"] == 1


def test_excluded_domains_never_get_send_cv() -> None:
    enriched = enrich_company(
        {
            "company": "Directory",
            "domain": "virgilio.it",
            "page_text": "azienda logistica export back office contatti",
            "emails": ["info@virgilio.it"],
            "contact_url": "https://virgilio.it/contatti",
            "is_employer": True,
        }
    )

    assert enriched["qualification"] == "Not Relevant"
    assert enriched["next_action"] == "Ignore"


def test_milestone_22_public_portals_are_not_profiled() -> None:
    selected, skipped = select_companies_for_profiling(
        [
            {"domain": "inps.it", "title": "Servizi aziende"},
            {"domain": "napoli.it", "title": "Comune di Napoli"},
            {"domain": "puglia.it", "title": "Regione Puglia"},
            {"domain": "na.it", "title": "Portale città"},
        ]
    )

    assert selected == []
    assert skipped["skipped_domain_excluded"] == 4
    assert skipped["skipped_public_sector"] == 4


def test_milestone_22_staffing_and_call_center_are_not_profiled() -> None:
    selected, skipped = select_companies_for_profiling(
        [
            {"domain": "adecco.it", "title": "Offerte lavoro"},
            {"domain": "tempimodernilavoro.com", "title": "Agenzia lavoro"},
            {"domain": "fibercallcenter.com", "title": "Call center"},
        ]
    )

    assert selected == []
    assert skipped["skipped_domain_excluded"] == 3
    assert skipped["skipped_staffing_agency"] == 2
    assert skipped["skipped_non_employer"] == 1


def test_milestone_22_advertising_directory_is_not_profiled() -> None:
    selected, skipped = select_companies_for_profiling(
        [{"domain": "agenziedipubblicita.org", "title": "Elenco agenzie pubblicità"}]
    )

    assert selected == []
    assert skipped["skipped_domain_excluded"] == 1
    assert skipped["skipped_directory"] == 1


def test_weak_employer_evidence_requires_specific_signal() -> None:
    assert not weak_employer_evidence(
        {"domain": "example.it", "title": "Elenco servizi Napoli", "snippet": "Lista generica"}
    )
    assert weak_employer_evidence(
        {"domain": "example.it", "title": "Azienda logistica import export", "snippet": "Contatti"}
    )


def test_milestone_41_latest_run_domains_are_not_profiled_by_category() -> None:
    selected, skipped = select_companies_for_profiling(
        [
            {"domain": "humangest.it", "title": "Agenzia lavoro"},
            {"domain": "aslnapoli1centro.it", "title": "ASL Napoli"},
            {"domain": "oraridiapertura24.it", "title": "Directory orari"},
            {"domain": "ildispariquotidiano.it", "title": "Notizie Campania"},
            {"domain": "uniroma1.it", "title": "Università"},
            {"domain": "similarweb.com", "title": "Analytics"},
            {"domain": "aon.com", "title": "Insurance"},
            {"domain": "apple.com", "title": "Corporate"},
            {"domain": "bolletta-acqua.it", "title": "Pagamento bollette"},
        ]
    )

    assert selected == []
    assert skipped["skipped_domain_excluded"] == 9
    assert skipped["skipped_staffing_agency"] == 1
    assert skipped["skipped_public_sector"] == 1
    assert skipped["skipped_directory"] == 1
    assert skipped["skipped_media"] == 1
    assert skipped["skipped_education"] == 1
    assert skipped["skipped_analytics_tool"] == 1
    assert skipped["skipped_bank_finance"] == 1
    assert skipped["skipped_non_target_big_corporate"] == 1
    assert skipped["skipped_non_employer"] == 1


def test_milestone_41_staffing_agencies_are_not_profiled() -> None:
    selected, skipped = select_companies_for_profiling(
        [
            {"domain": "adecco.it", "title": "Offerte lavoro"},
            {"domain": "humangest.it", "title": "Agenzia lavoro"},
            {"domain": "openjobmetis.it", "title": "Agenzia lavoro"},
            {"domain": "generazionevincente.it", "title": "Agenzia lavoro"},
            {"domain": "during.it", "title": "Agenzia lavoro"},
            {"domain": "gesforsrl.it", "title": "Agenzia lavoro"},
        ]
    )

    assert selected == []
    assert skipped["skipped_domain_excluded"] == 6
    assert skipped["skipped_staffing_agency"] == 6


def test_milestone_41_excluded_staffing_agency_never_gets_send_cv() -> None:
    enriched = enrich_company(
        {
            "company": "Adecco",
            "domain": "adecco.it",
            "page_text": "azienda logistica export back office contatti",
            "emails": ["info@adecco.it"],
            "contact_url": "https://adecco.it/contatti",
            "career_page": "https://adecco.it/lavora-con-noi",
            "is_employer": True,
        }
    )

    assert enriched["next_action"] != "Send CV"
    assert enriched["next_action"] == "Manual Review"


def test_milestone_41_latest_false_positive_domains_never_get_send_cv() -> None:
    for domain in ("lavoratorio.it", "traspare.com"):
        enriched = enrich_company(
            {
                "company": domain,
                "domain": domain,
                "page_text": "azienda logistica export back office contatti lavora con noi",
                "emails": [f"info@{domain}"],
                "contact_url": f"https://{domain}/contatti",
                "career_page": f"https://{domain}/lavora-con-noi",
                "is_employer": True,
            }
        )

        assert enriched["next_action"] == "Ignore"
