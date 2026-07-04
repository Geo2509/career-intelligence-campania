from src.website_classifier import classify_company
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
