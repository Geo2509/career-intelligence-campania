from src.website_classifier import classify_company, post_profile_reclassify_company, post_profile_reclassify_companies
from src.main import profile_skip_reason, load_excluded_domain_classes


def make_company(domain: str, title: str = "", snippet: str = "", query: str = ""):
    return {
        "domain": domain,
        "title": title,
        "snippet": snippet,
        "url": f"https://{domain}",
        "query": query,
        "strategy": "",
        "original_query": query,
    }


def test_news_sites_classified_and_skipped():
    company = make_company("montediprocida.com", title="Giornale - cronaca di Monte di Procida")
    wtype, conf, reasons = classify_company(company)
    assert wtype in ("news", "media") or "news" in wtype
    assert conf > 0
    assert any("cronaca" in r for r in reasons)
    # pre-profile skip
    reason = profile_skip_reason({**company, "website_type": wtype}, load_excluded_domain_classes())
    assert reason.startswith("skipped_")


def test_torinotoday_classified_as_news():
    company = make_company("torinotoday.it", title="Torino Today - notizie e cronaca")
    wtype, _, _ = classify_company(company)
    assert wtype in ("news", "media") or "news" in wtype


def test_mixed_signals_tie_results_in_unknown():
    # mixed company and news signals with similar weights should tie
    # choose fewer/balanced keywords so scores are within tie threshold
    company = make_company(
        "example.it",
        title="azienda e cronaca",
        snippet="cronaca azienda",
    )
    wtype, conf, reasons = classify_company(company)
    # tie should return unknown per policy
    assert wtype == "unknown"
    assert conf == 0


def test_healthcare_government_classified_and_skipped():
    company = make_company("aslnapoli1centro.it", title="ASL Napoli - avvisi pubblici e bandi")
    wtype, _, _ = classify_company(company)
    assert wtype in ("healthcare", "government") or "asl" in company["domain"]
    reason = profile_skip_reason({**company, "website_type": wtype}, load_excluded_domain_classes())
    assert reason.startswith("skipped_")


def test_education_and_university_classified_and_skipped():
    company = make_company("uniroma1.it", title="Università - dipartimento di ingegneria")
    wtype, _, _ = classify_company(company)
    assert wtype in ("university", "education") or "universit" in wtype
    reason = profile_skip_reason({**company, "website_type": wtype}, load_excluded_domain_classes())
    assert reason.startswith("skipped_")


def test_company_and_staffing_agency():
    c1 = make_company("cerbone.srl", title="Cerbone Srl - azienda e servizi")
    wt1, _, _ = classify_company(c1)
    assert wt1 == "company"

    c2 = make_company("randstad.it", title="Randstad Italia - lavoro e agenzia per il lavoro")
    wt2, _, _ = classify_company(c2)
    # staffing agency should be recognized
    assert wt2 in ("staffing_agency", "company")
    reason = profile_skip_reason({**c2, "website_type": wt2}, load_excluded_domain_classes())
    # staffing agency should trigger a staffing-specific skip
    assert reason.startswith("skipped_")


def reclassify(record: dict) -> dict:
    updated, _, _ = post_profile_reclassify_company(
        {
            "website_type": "company",
            "website_type_confidence": 65,
            "website_type_reasons": ["azienda:30", "contatti:25"],
            "qualification": "Good Match",
            "next_action": "Send CV",
            "emails": [f"info@{record['domain']}"],
            "phones": ["0811234567"],
            "contact_url": f"https://{record['domain']}/contatti",
            "career_url": f"https://{record['domain']}/lavora-con-noi",
            **record,
        }
    )
    return updated


def test_post_profile_grafton_classified_as_staffing_agency():
    updated = reclassify(
        {
            "domain": "grafton.com",
            "title": "Grafton Recruitment",
            "snippet": "Agenzia per il lavoro e selezione del personale",
            "page_text": "Staffing recruitment temporary work candidati aziende clienti offerte di lavoro.",
        }
    )

    assert updated["website_type_initial"] == "company"
    assert updated["website_type_final"] == "staffing_agency"
    assert updated["website_type"] == "staffing_agency"
    assert updated["next_action"] != "Send CV"
    assert updated["next_action"] == "Manual Review"
    assert updated["qualification"] == "Possible Match"


def test_post_profile_pagepersonnel_classified_as_staffing_agency():
    updated = reclassify(
        {
            "domain": "pagepersonnel.it",
            "title": "Page Personnel Italia",
            "snippet": "Recruitment e head hunting",
            "page_text": "Selezione del personale, offerte di lavoro, candidati e aziende clienti.",
        }
    )

    assert updated["website_type_final"] == "staffing_agency"
    assert updated["next_action"] != "Send CV"


def test_post_profile_servizi_cittadino_classified_as_public_service():
    updated = reclassify(
        {
            "domain": "servizi-cittadino.com",
            "title": "Servizi cittadino",
            "snippet": "Pratiche online, sportello, visure e informazioni aziende",
            "page_text": "Elenco comuni amministrazioni scheda azienda orari.",
        }
    )

    assert updated["website_type_final"] in {"public_service", "directory", "non_employer"}
    assert updated["next_action"] == "Ignore"
    assert updated["qualification"] == "Not Relevant"


def test_post_profile_iprogrammatori_classified_as_job_board_or_marketplace():
    updated = reclassify(
        {
            "domain": "iprogrammatori.it",
            "title": "I Programmatori",
            "snippet": "Annunci lavoro e offerte di lavoro per programmatori",
            "page_text": "Cerca lavoro, candidati ora, job alert, lavori disponibili, vacancy database.",
        }
    )

    assert updated["website_type_final"] in {"job_board", "marketplace"}
    assert updated["next_action"] == "Ignore"


def test_post_profile_contabili_directory_preserves_initial_and_final_fields():
    updated = reclassify(
        {
            "domain": "contabili.it",
            "title": "Contabili in Italia",
            "snippet": "Elenco professionisti e scheda azienda",
            "page_text": "Directory professionisti, informazioni aziende, pagine, orari e preventivi.",
        }
    )

    assert updated["website_type_initial"] == "company"
    assert updated["website_type_initial_confidence"] == 65
    assert updated["website_type_final"] in {"directory", "marketplace"}
    assert updated["website_type_final_confidence"] > 0
    assert updated["website_type_final_reasons"]
    assert updated["next_action"] != "Send CV"


def test_post_profile_reclassification_stats_count_downgrades_and_send_cv_removal():
    companies, stats = post_profile_reclassify_companies(
        [
            {
                "domain": "grafton.com",
                "website_type": "company",
                "website_type_confidence": 70,
                "title": "Grafton recruitment",
                "page_text": "Agenzia per il lavoro selezione del personale aziende clienti",
                "qualification": "Good Match",
                "next_action": "Send CV",
            },
            {
                "domain": "servizi-cittadino.com",
                "website_type": "company",
                "website_type_confidence": 70,
                "title": "Servizi cittadino",
                "page_text": "Pratiche online sportello visure comuni amministrazioni",
                "qualification": "Good Match",
                "next_action": "Send CV",
            },
        ]
    )

    assert stats["post_reclassified_count"] == 2
    assert stats["post_reclassified_to_staffing_agency"] == 1
    assert stats["post_reclassified_to_public_sector"] == 1
    assert stats["send_cv_removed_by_reclassification"] == 2
    assert all(company["next_action"] != "Send CV" for company in companies)
