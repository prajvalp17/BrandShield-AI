
from detection.clustering import find_suspicious_clusters


def test_exact_contact_number_links_flagged_candidates():
    results = [
        {
            "entity_id": "app_01",
            "status": "FLAGGED",
            "indicators": {"contact_number": "+91 98765-43210"},
        },
        {
            "entity_id": "social_01",
            "status": "FLAGGED",
            "indicators": {"contact_number": "919876543210"},
        },
    ]

    clusters = find_suspicious_clusters(results)

    assert len(clusters) == 1
    assert clusters[0]["linked_candidate_ids"] == ["app_01", "social_01"]
    assert clusters[0]["link_reasons"][0]["indicator_type"] == "contact_number"


def test_non_flagged_candidates_are_not_linked():
    results = [
        {
            "entity_id": "app_01",
            "status": "NOT_FLAGGED",
            "indicators": {"contact_number": "123456789"},
        },
        {
            "entity_id": "app_02",
            "status": "FLAGGED",
            "indicators": {"contact_number": "123456789"},
        },
    ]

    assert find_suspicious_clusters(results) == []


def test_full_redirect_url_must_match():
    results = [
        {
            "entity_id": "app_01",
            "status": "FLAGGED",
            "indicators": {"redirect_url": "https://example.com/login"},
        },
        {
            "entity_id": "app_02",
            "status": "FLAGGED",
            "indicators": {"redirect_url": "https://example.com/pay"},
        },
    ]

    assert find_suspicious_clusters(results) == []


def test_identical_full_redirect_urls_link():
    results = [
        {
            "entity_id": "app_01",
            "status": "FLAGGED",
            "indicators": {"redirect_url": "HTTPS://EXAMPLE.COM/login"},
        },
        {
            "entity_id": "app_02",
            "status": "FLAGGED",
            "indicators": {"redirect_url": "https://example.com/login"},
        },
    ]

    clusters = find_suspicious_clusters(results)

    assert len(clusters) == 1
    assert clusters[0]["link_reasons"][0]["indicator_type"] == "redirect_url"


def test_one_digit_apart_phone_numbers_do_not_link():
    results = [
        {
            "entity_id": "app_01",
            "status": "FLAGGED",
            "indicators": {"contact_number": "9876543210"},
        },
        {
            "entity_id": "app_02",
            "status": "FLAGGED",
            "indicators": {"contact_number": "9876543211"},
        },
    ]

    assert find_suspicious_clusters(results) == []


def test_missing_indicators_do_not_link():
    results = [
        {
            "entity_id": "app_01",
            "status": "FLAGGED",
            "indicators": {},
        },
        {
            "entity_id": "app_02",
            "status": "FLAGGED",
            "indicators": {},
        },
    ]

    assert find_suspicious_clusters(results) == []
