from src.export_filter import apply_final_export_filter, export_filter_decision


def test_blacklisted_social_and_video_domains_are_removed() -> None:
    for domain in ("youtube.com", "facebook.com", "instagram.com"):
        decision = export_filter_decision({"domain": domain, "url": f"https://{domain}/x"})

        assert decision["remove"] is True
        assert decision["blacklist"] is True


def test_travel_and_platform_domains_are_removed() -> None:
    for domain in ("tripadvisor.it", "travorium.com", "similarweb.com", "clutch.co"):
        decision = export_filter_decision({"domain": domain, "url": f"https://{domain}/x"})

        assert decision["remove"] is True
        assert decision["blacklist"] is True


def test_direct_employer_domain_is_not_removed() -> None:
    decision = export_filter_decision(
        {
            "domain": "azienda-logistica.it",
            "website_type": "company",
            "is_employer": True,
            "emails": ["info@azienda-logistica.it"],
            "has_contact_page": True,
        }
    )

    assert decision["remove"] is False


def test_career_page_company_is_not_removed() -> None:
    decision = export_filter_decision(
        {
            "domain": "azienda.it",
            "website_type": "company",
            "career_url": "https://azienda.it/lavora-con-noi",
            "has_careers_page": True,
        }
    )

    assert decision["remove"] is False


def test_hr_email_company_is_not_removed() -> None:
    decision = export_filter_decision(
        {
            "domain": "azienda.it",
            "website_type": "company",
            "hr_email": "hr@azienda.it",
            "emails": ["hr@azienda.it"],
        }
    )

    assert decision["remove"] is False


def test_never_export_type_removed_without_direct_employer_evidence() -> None:
    filtered, report = apply_final_export_filter(
        [
            {"company": "Directory", "domain": "directory.example", "website_type": "directory_only"},
            {"company": "Employer", "domain": "employer.it", "website_type": "company"},
        ]
    )

    assert [company["company"] for company in filtered] == ["Employer"]
    assert report["removed_by_export_filter"] == 1
    assert report["removed_non_employers"] == 1
    assert report["removed_domains"][0]["domain"] == "directory.example"


def test_never_export_type_kept_with_direct_employer_evidence() -> None:
    decision = export_filter_decision(
        {
            "domain": "employer.it",
            "website_type": "non_employer",
            "hr_email": "hr@employer.it",
            "career_url": "https://employer.it/careers",
        }
    )

    assert decision["remove"] is False
